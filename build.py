"""Merge LEAD, ACS, and boundaries into one analysis-ready tract dataset,
flag unreliable tracts, and write a validation report."""
from __future__ import annotations

from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import libpysal
import pandas as pd

from . import acs, config as C, geo, lead


def flag_quality(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["flag_few_households"] = df["households"].fillna(0) < C.MIN_HOUSEHOLDS
    df["flag_no_burden"] = df["burden"].isna()
    cv_cols = [c for c in df.columns if c.endswith("_cv")]
    key_cvs = ["median_hh_income_cv", "pct_renter_cv", "pct_pre1950_cv"]
    df["flag_unreliable_acs"] = (df[[c for c in key_cvs if c in cv_cols]] > C.CV_UNRELIABLE).any(axis=1)
    df["analysis_sample"] = ~(df["flag_few_households"] | df["flag_no_burden"]
                              | df["median_hh_income"].isna())
    return df


def citywide_burden(df: pd.DataFrame) -> float:
    s = df[df["households"] > 0]
    energy = s[["elep_total", "gasp_total", "fulp_total"]].sum().sum()
    return 100 * energy / s["hincp_total"].sum()


def unit_check(city_burden: float) -> str | None:
    """Catch a units mistake (e.g. monthly costs read as annual) before modeling."""
    if city_burden < 1.0:
        return ("Citywide burden is below 1%, far under ACEEE's ~2-3%. LEAD cost columns "
                "may be monthly rather than annual; check the data dictionary.")
    if city_burden > 10.0:
        return ("Citywide burden is above 10%, far over ACEEE's ~2-3%. Income or cost "
                "columns may be in different units; check the data dictionary.")
    return None


def run(tract_zip, place_zip, lead_zip, acs_cov_json, acs_cost_json):
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    (C.REPORTS / "figures").mkdir(exist_ok=True)

    print("Selecting Chicago tracts")
    gdf = geo.chicago_tracts(tract_zip, place_zip)
    print(f"  {len(gdf)} tracts")

    print("Computing LEAD energy burden")
    lead_t = lead.load(lead_zip)

    print("Building ACS covariates")
    cov = acs.build_covariates(acs.read_covariates(acs_cov_json))
    costs = acs.cost_index(acs_cost_json)

    df = (gdf.merge(lead_t, on="GEOID", how="left")
             .merge(cov, left_on="GEOID", right_index=True, how="left")
             .merge(costs, left_on="GEOID", right_index=True, how="left"))
    df = flag_quality(df)

    df.to_file(C.PROCESSED / "chicago_tracts.gpkg", driver="GPKG")
    df.drop(columns="geometry").to_csv(C.PROCESSED / "chicago_tracts.csv", index=False)

    sample = df[df["analysis_sample"]].reset_index(drop=True)
    for kind in ("queen", "knn"):
        w = geo.weights(sample, kind)
        f = libpysal.io.open(str(C.PROCESSED / f"weights_{kind}.gal"), "w")
        f.write(w)
        f.close()
    sample[["GEOID"]].to_csv(C.PROCESSED / "weights_order.csv", index=False)

    write_report(df, sample)
    print(f"Done. Outputs in {C.PROCESSED} and {C.REPORTS}")
    return df


# ---------------------------------------------------------------- report
def _map(gdf, col, title, path):
    fig, ax = plt.subplots(figsize=(6, 8))
    gdf.plot(column=col, scheme="quantiles", k=5, cmap="YlOrRd", legend=True,
             edgecolor="white", linewidth=0.1, ax=ax,
             missing_kwds={"color": "#dddddd", "label": "No data"},
             legend_kwds={"loc": "lower left", "fmt": "{:.1f}", "title": "Percent of income"})
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_report(df, sample):
    city = citywide_burden(sample)
    warn = unit_check(city)
    b = sample["burden"]
    lines = [
        "# Data Validation Report",
        f"_Generated {date.today().isoformat()} by `run_pipeline.py`_",
        "",
        "## Coverage",
        f"- Chicago census tracts (2020 boundaries): **{len(df)}**",
        f"- Tracts in the analysis sample: **{len(sample)}**",
        f"- Flagged, fewer than {C.MIN_HOUSEHOLDS} households: {int(df['flag_few_households'].sum())}",
        f"- Flagged, missing LEAD burden: {int(df['flag_no_burden'].sum())}",
        f"- Flagged, unreliable ACS estimate (CV > {C.CV_UNRELIABLE:.0%}): {int(df['flag_unreliable_acs'].sum())}",
        f"- Households covered: {sample['households'].sum():,.0f}",
        "",
        "## Energy burden (LEAD)",
        f"- Citywide burden, all households pooled: **{city:.2f}%**",
        f"- Median tract burden: {b.median():.2f}%",
        f"- 10th / 90th percentile tract: {b.quantile(.1):.2f}% / {b.quantile(.9):.2f}%",
        f"- Highest tract: {b.max():.2f}%",
        f"- Tracts with average burden above 6%: {(b > C.BURDEN_HIGH).sum()}",
        f"- Tracts with average burden above 10%: {(b > C.BURDEN_SEVERE).sum()}",
        "",
        "## Benchmark comparison",
        "| Source | Figure | Value |",
        "|---|---|---|",
        f"| This project (LEAD {C.LEAD_YEAR}) | Citywide burden | {city:.2f}% |",
        f"| ACEEE (2020), Chicago metro | Median burden, all households | {C.ACEEE_BENCHMARKS['aceee_2020_median_all']}% |",
        f"| ACEEE (2024), Chicago | Median burden, all households | {C.ACEEE_BENCHMARKS['aceee_2024_median_all']}% |",
        "",
        "ACEEE reports household medians for the metro area, while our figure pools the "
        "city's households, so we expect it to be in the same range but not identical.",
    ]
    if warn:
        lines += ["", f"> **Warning:** {warn}"]

    pairs = [("elec_cost_avg", "acs_electricity_cost_annual", "Electricity"),
             ("gas_cost_avg", "acs_gas_cost_annual", "Gas")]
    lines += ["", "## LEAD vs. ACS cost brackets",
              "Independent check: correlation across tracts between LEAD's modeled costs "
              "and costs estimated from ACS tables B25132 and B25133.", "",
              "| Fuel | Correlation | LEAD median | ACS median |", "|---|---|---|---|"]
    for a, c, label in pairs:
        if a in sample and c in sample:
            r = sample[[a, c]].corr().iloc[0, 1]
            lines.append(f"| {label} | {r:.2f} | ${sample[a].median():,.0f} | ${sample[c].median():,.0f} |")

    top = sample.nlargest(10, "burden")[["GEOID", "burden", "median_hh_income", "pct_pre1950", "pct_renter"]]
    lines += ["", "## Ten highest-burden tracts", "",
              "| Tract | Burden | Median income | Built pre-1950 | Renter |", "|---|---|---|---|---|"]
    for _, r in top.iterrows():
        lines.append(f"| {r.GEOID} | {r.burden:.1f}% | ${r.median_hh_income:,.0f} | "
                     f"{r.pct_pre1950:.0f}% | {r.pct_renter:.0f}% |")

    _map(df, "burden", "Household energy burden by census tract",
         C.REPORTS / "figures" / "burden_map.png")
    lines += ["", "## Map", "![Energy burden map](figures/burden_map.png)", ""]
    (C.REPORTS / "validation_report.md").write_text("\n".join(lines))
