"""Stage 2: exploratory spatial analysis.

Answers Research Question 1: is energy burden spatially clustered, and where are
the statistically significant hotspots?

* Global Moran's I: one number for the whole city. Positive and significant means
  high-burden tracts tend to sit next to other high-burden tracts.
* Local Moran's I (LISA; Anselin, 1995): one test per tract, sorting each into
  High-High (hotspot), Low-Low (coldspot), High-Low or Low-High (outliers), or
  not significant. Because we run hundreds of tests, significance is judged with
  a false discovery rate (FDR) correction, not a plain p < 0.05.
"""
from __future__ import annotations

from pathlib import Path

import esda
import geopandas as gpd
import libpysal
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from . import config as C, geo

OUTCOMES = {
    "burden": "Energy burden (% of income)",
    "share_severe": "Households above 10% burden (%)",
}
DESCRIBE = {
    "burden": "Energy burden (%)",
    "share_high": "Households above 6% burden (%)",
    "share_severe": "Households above 10% burden (%)",
    "energy_cost_avg": "Avg. annual energy cost ($)",
    "median_hh_income": "Median household income ($)",
    "pct_black": "Black, non-Hispanic (%)",
    "pct_hispanic": "Hispanic or Latino (%)",
    "pct_pre1950": "Housing built before 1950 (%)",
    "pct_renter": "Renter-occupied (%)",
    "pct_multifamily": "Units in 5+ unit buildings (%)",
}
CLUSTER_COLORS = {
    "High-High": "#d7191c",
    "Low-Low": "#2c7bb6",
    "Low-High": "#abd9e9",
    "High-Low": "#fdae61",
    "Not significant": "#e6e6e6",
}
QUAD = {1: "High-High", 2: "Low-High", 3: "Low-Low", 4: "High-Low"}


# ---------------------------------------------------------------- loading
def load_sample() -> tuple[gpd.GeoDataFrame, dict]:
    """Analysis-sample tracts plus spatial weights built in the same row order.

    Weights are rebuilt from geometry (it takes a second) rather than read from
    the .gal files, so tract order can never drift out of alignment.
    """
    gdf = gpd.read_file(C.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["analysis_sample"].astype(bool)].reset_index(drop=True)
    return gdf, {kind: geo.weights(gdf, kind) for kind in ("queen", "knn")}


def attach_community_areas(gdf: gpd.GeoDataFrame, ca_path: Path | None) -> gpd.GeoDataFrame:
    """Label each tract with the community area containing its interior point."""
    gdf = gdf.copy()
    gdf["community_area"] = pd.NA
    if ca_path is None or not Path(ca_path).exists():
        return gdf
    ca = gpd.read_file(ca_path).to_crs(gdf.crs)
    name_col = next((c for c in ca.columns if c.lower() in ("community", "community_area", "name")), None)
    if name_col is None:
        return gdf
    pts = gdf[["GEOID"]].copy()
    pts = gpd.GeoDataFrame(pts, geometry=gdf.representative_point(), crs=gdf.crs)
    joined = gpd.sjoin(pts, ca[[name_col, "geometry"]], predicate="within", how="left")
    joined = joined[~joined.index.duplicated()]
    gdf["community_area"] = joined[name_col].str.title().values
    return gdf


# ---------------------------------------------------------------- statistics
def describe(gdf: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in DESCRIBE if c in gdf]
    d = gdf[cols].describe(percentiles=[.1, .25, .5, .75, .9]).T
    d.index = [DESCRIBE[c] for c in cols]
    return d[["count", "mean", "std", "min", "10%", "25%", "50%", "75%", "90%", "max"]]


def global_moran(y: np.ndarray, w) -> dict:
    np.random.seed(C.SEED)
    m = esda.Moran(y, w, permutations=C.PERMUTATIONS)
    return {"I": m.I, "expected_I": m.EI, "z": m.z_sim, "p_perm": m.p_sim}


def local_moran(y: np.ndarray, w) -> pd.DataFrame:
    try:  # two-sided p-values: the conservative choice, and esda's future default
        lm = esda.Moran_Local(y, w, permutations=C.PERMUTATIONS, seed=C.SEED,
                              alternative="two-sided")
    except TypeError:  # older esda without the option
        lm = esda.Moran_Local(y, w, permutations=C.PERMUTATIONS, seed=C.SEED)
    p = lm.p_sim
    fdr_cut = esda.fdr(p, C.ALPHA)
    quad = pd.Series(lm.q).map(QUAD)
    return pd.DataFrame({
        "lisa_I": lm.Is,
        "lisa_p": p,
        "lisa_quadrant": quad,
        "cluster_p05": np.where(p < C.ALPHA, quad, "Not significant"),
        "cluster_fdr": np.where(p <= fdr_cut, quad, "Not significant"),
    }), fdr_cut


# ---------------------------------------------------------------- figures
def fig_small_multiples(gdf, path):
    cols = [c for c in ["burden", "median_hh_income", "pct_black", "pct_hispanic",
                        "pct_pre1950", "pct_renter"] if c in gdf]
    fig, axes = plt.subplots(2, 3, figsize=(12, 10))
    for ax, col in zip(axes.flat, cols):
        cmap = "YlGnBu" if col == "median_hh_income" else "YlOrRd"
        gdf.plot(column=col, scheme="quantiles", k=5, cmap=cmap, legend=True, ax=ax,
                 edgecolor="white", linewidth=0.05,
                 legend_kwds={"loc": "upper right", "fontsize": 7, "fmt": "{:,.0f}"
                              if col == "median_hh_income" else "{:.1f}"})
        ax.set_title(DESCRIBE.get(col, col), fontsize=10)
        ax.set_axis_off()
    for ax in axes.flat[len(cols):]:
        ax.set_axis_off()
    fig.suptitle("Energy burden and neighborhood characteristics (quintiles)", fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_cluster_map(gdf, col, title, path):
    fig, ax = plt.subplots(figsize=(6, 8))
    for label, color in CLUSTER_COLORS.items():
        sub = gdf[gdf[col] == label]
        if len(sub):
            sub.plot(color=color, edgecolor="white", linewidth=0.1, ax=ax)
    handles = [Patch(color=c, label=f"{k} ({(gdf[col] == k).sum()})") for k, c in CLUSTER_COLORS.items()]
    ax.legend(handles=handles, loc="upper right", fontsize=8, title="LISA cluster (FDR 5%)")
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_moran_scatter(y, w, I, title, path):
    z = (y - y.mean()) / y.std()
    lag = libpysal.weights.lag_spatial(w, z)
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.scatter(z, lag, s=8, alpha=0.5, color="#555555")
    b = np.polyfit(z, lag, 1)
    xs = np.linspace(z.min(), z.max(), 50)
    ax.plot(xs, b[0] * xs + b[1], color="#d7191c", lw=1.5, label=f"Slope = Moran's I = {I:.2f}")
    ax.axhline(0, color="gray", lw=0.6)
    ax.axvline(0, color="gray", lw=0.6)
    for (x, yy, t) in [(.97, .97, "High-High"), (.03, .03, "Low-Low"), (.03, .97, "Low-High"), (.97, .03, "High-Low")]:
        ax.text(x, yy, t, transform=ax.transAxes, ha="right" if x > .5 else "left",
                va="top" if yy > .5 else "bottom", fontsize=8, color="gray")
    ax.set_xlabel("Tract value (standardized)")
    ax.set_ylabel("Average of neighboring tracts (standardized)")
    ax.set_title(title)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 0.07), fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- run
def run(community_areas: Path | None = None) -> gpd.GeoDataFrame:
    figs = C.REPORTS / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    gdf, W = load_sample()
    gdf = attach_community_areas(gdf, community_areas)
    print(f"  {len(gdf)} tracts; queen islands: {len(W['queen'].islands)}")

    desc = describe(gdf)
    desc.to_csv(C.REPORTS / "descriptive_statistics.csv")

    globals_ = []
    fdr_cuts = {}
    for col in OUTCOMES:
        y = gdf[col].astype(float).to_numpy()
        if np.isnan(y).any():
            raise ValueError(f"{col} has missing values in the analysis sample")
        for kind, w in W.items():
            globals_.append({"variable": col, "weights": kind, **global_moran(y, w)})
        lisa, cut = local_moran(y, W["queen"])
        fdr_cuts[col] = cut
        gdf[[f"{col}_{c}" for c in lisa.columns]] = lisa.to_numpy()
        fig_cluster_map(gdf, f"{col}_cluster_fdr", f"LISA clusters: {OUTCOMES[col]}",
                        figs / f"lisa_{col}.png")
    glob = pd.DataFrame(globals_)
    glob.to_csv(C.REPORTS / "global_morans_i.csv", index=False)

    y = gdf["burden"].astype(float).to_numpy()
    I_q = glob.query("variable == 'burden' and weights == 'queen'")["I"].iloc[0]
    fig_moran_scatter(y, W["queen"], I_q, "Moran scatterplot: energy burden", figs / "moran_scatter_burden.png")
    fig_small_multiples(gdf, figs / "small_multiples.png")

    keep = ["GEOID", "community_area", "burden", "share_severe", "median_hh_income",
            "pct_black", "pct_hispanic", "pct_pre1950", "pct_renter",
            "burden_lisa_I", "burden_lisa_p", "burden_cluster_fdr", "burden_cluster_p05",
            "share_severe_cluster_fdr"]
    gdf[[c for c in keep if c in gdf]].to_csv(C.PROCESSED / "lisa_results.csv", index=False)
    gdf.to_file(C.PROCESSED / "lisa_results.gpkg", driver="GPKG")

    write_report(gdf, desc, glob, fdr_cuts)
    print(f"  done; see {C.REPORTS / 'spatial_analysis_report.md'}")
    return gdf


def _fmt_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def write_report(gdf, desc, glob, fdr_cuts):
    L = ["# Stage 2: Exploratory Spatial Analysis", "",
         f"Analysis sample: **{len(gdf)} tracts**. Permutation tests use "
         f"{C.PERMUTATIONS:,} permutations (seed {C.SEED}).", "",
         "## Descriptive statistics", "",
         "| Variable | Mean | SD | Min | Median | Max |", "|---|---|---|---|---|---|"]
    for name, r in desc.iterrows():
        f = "{:,.0f}" if "$" in name else "{:.2f}"
        L.append(f"| {name} | {f.format(r['mean'])} | {f.format(r['std'])} | "
                 f"{f.format(r['min'])} | {f.format(r['50%'])} | {f.format(r['max'])} |")

    L += ["", "![Small multiples](figures/small_multiples.png)", "",
          "## Global spatial autocorrelation (Moran's I)", "",
          "| Variable | Weights | Moran's I | E[I] | z (sim) | p (perm) |", "|---|---|---|---|---|---|"]
    for _, r in glob.iterrows():
        L.append(f"| {OUTCOMES[r.variable]} | {r.weights} | {r.I:.3f} | {r.expected_I:.4f} | "
                 f"{r.z:.2f} | {_fmt_p(r.p_perm)} |")
    I = glob.query("variable == 'burden' and weights == 'queen'").iloc[0]
    verdict = ("positive and statistically significant: high-burden tracts tend to be next to "
               "other high-burden tracts" if I.I > 0 and I.p_perm < C.ALPHA else
               "not statistically significant: no evidence of clustering at the city scale")
    L += ["", f"**Reading:** With queen contiguity, Moran's I for energy burden is {I.I:.3f} "
          f"(p {_fmt_p(I.p_perm)}), which is {verdict}.", "",
          "![Moran scatterplot](figures/moran_scatter_burden.png)", "",
          "## Local clusters (LISA)", "",
          f"Significance uses a 5% false discovery rate. For energy burden the FDR cutoff is "
          f"p <= {fdr_cuts['burden']:.4f}; a plain p < 0.05 rule is shown for comparison.", "",
          "| Cluster type | FDR 5% | Unadjusted p < 0.05 |", "|---|---|---|"]
    for k in CLUSTER_COLORS:
        L.append(f"| {k} | {(gdf['burden_cluster_fdr'] == k).sum()} | {(gdf['burden_cluster_p05'] == k).sum()} |")
    L += ["", "![LISA clusters, burden](figures/lisa_burden.png)",
          "![LISA clusters, severe burden share](figures/lisa_share_severe.png)", ""]

    hot = gdf[gdf["burden_cluster_fdr"] == "High-High"]
    if len(hot):
        L += ["## Hotspot tracts (High-High, FDR 5%)", ""]
        if hot["community_area"].notna().any():
            by_ca = (hot.groupby("community_area")
                        .agg(tracts=("GEOID", "size"), mean_burden=("burden", "mean"))
                        .sort_values("tracts", ascending=False))
            L += ["| Community area | Hotspot tracts | Mean burden |", "|---|---|---|"]
            L += [f"| {ca} | {int(r.tracts)} | {r.mean_burden:.1f}% |" for ca, r in by_ca.iterrows()]
            L.append("")
        hs = hot.agg({"burden": "mean", "median_hh_income": "median", "pct_pre1950": "mean",
                      "pct_renter": "mean"})
        rest = gdf[gdf["burden_cluster_fdr"] != "High-High"].agg(
            {"burden": "mean", "median_hh_income": "median", "pct_pre1950": "mean", "pct_renter": "mean"})
        L += ["### Hotspots compared with all other tracts", "",
              "| | Hotspots | All other tracts |", "|---|---|---|",
              f"| Mean burden | {hs.burden:.1f}% | {rest.burden:.1f}% |",
              f"| Median household income | ${hs.median_hh_income:,.0f} | ${rest.median_hh_income:,.0f} |",
              f"| Housing built before 1950 | {hs.pct_pre1950:.0f}% | {rest.pct_pre1950:.0f}% |",
              f"| Renter-occupied | {hs.pct_renter:.0f}% | {rest.pct_renter:.0f}% |", ""]
    L += ["## Notes", "",
          "- These are tract averages. They describe neighborhoods, not individual households.",
          "- LISA finds where burden clusters; it does not explain why. That is Stage 3.",
          "- The k-nearest-neighbor result (k = 6) checks that clustering is not an artifact "
          "of how tract borders happen to touch."]
    (C.REPORTS / "spatial_analysis_report.md").write_text("\n".join(L))
