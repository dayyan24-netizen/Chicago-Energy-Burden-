"""Load the DOE LEAD Tool data and compute energy burden for each census tract.

LEAD splits each tract's households into cohorts (income bracket x tenure x
building type, and so on). Each row holds a household count and either totals
("HINCP*UNITS") or averages ("HINCP") of income and energy spending for that
cohort. We add the cohorts back up to the tract.

Tract energy burden = total energy spending / total household income x 100.
This is the burden of the "average household" in the tract, the measure used by
DOE and by Moore & Webb (2022). Averaging cohort-level burdens instead would
overweight tiny low-income cohorts with extreme ratios.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

FIELDS = ["HINCP", "ELEP", "GASP", "FULP"]  # income, electricity, gas, other fuel


def _pick_tract_csv(zf: zipfile.ZipFile) -> str:
    """Find the census-tract file inside a LEAD state zip.

    Every income framework (AMI, FPL, SMI, LLSI) partitions the same households,
    so tract totals are identical; AMI is preferred only for consistency.
    """
    csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    tract = [n for n in csvs if "tract" in n.lower()]
    if not tract:
        raise ValueError(f"No census-tract CSV found in LEAD zip. Files: {csvs}")
    ami = [n for n in tract if "ami" in Path(n).name.lower()]
    return sorted(ami or tract)[0]


def _find_col(cols: list[str], field: str) -> tuple[str, bool]:
    """Return (column name, is_total) for a LEAD field, matching case-insensitively.

    "ELEP*UNITS" means a cohort total; plain "ELEP" means a cohort average.
    """
    norm = {c: re.sub(r"[\s_]", "", c.upper()) for c in cols}
    for c, n in norm.items():
        if n == f"{field}*UNITS":
            return c, True
    for c, n in norm.items():
        if n == field:
            return c, False
    raise KeyError(f"LEAD file has no column for {field}. Columns: {cols}")


def read_lead(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        name = _pick_tract_csv(zf)
        print(f"  reading {name}")
        raw = pd.read_csv(io.BytesIO(zf.read(name)), dtype=str, low_memory=False)
    return raw


def tract_burden(raw: pd.DataFrame) -> pd.DataFrame:
    """Collapse LEAD cohort rows to one row per tract."""
    cols = list(raw.columns)
    fip = next((c for c in cols if c.strip().upper() in ("FIP", "FIPS", "GEOID")), None)
    if fip is None:
        raise KeyError(f"LEAD file has no tract ID column (FIP). Columns: {cols}")
    units = next((c for c in cols if c.strip().upper() == "UNITS"), None)
    if units is None:
        raise KeyError(f"LEAD file has no UNITS column. Columns: {cols}")

    df = pd.DataFrame({"GEOID": raw[fip].str.replace(r"\.0$", "", regex=True).str.zfill(11)})
    df["households"] = pd.to_numeric(raw[units], errors="coerce").fillna(0)
    for f in FIELDS:
        col, is_total = _find_col(cols, f)
        v = pd.to_numeric(raw[col], errors="coerce").fillna(0)
        df[f.lower() + "_total"] = v if is_total else v * df["households"]

    t = df.groupby("GEOID", as_index=False).sum(numeric_only=True)
    energy = t[["elep_total", "gasp_total", "fulp_total"]].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t["energy_cost_avg"] = energy / t["households"]
        t["elec_cost_avg"] = t["elep_total"] / t["households"]
        t["gas_cost_avg"] = t["gasp_total"] / t["households"]
        t["income_avg"] = t["hincp_total"] / t["households"]
        t["burden"] = 100 * energy / t["hincp_total"]
        t["burden_elec"] = 100 * t["elep_total"] / t["hincp_total"]
        t["burden_gas"] = 100 * t["gasp_total"] / t["hincp_total"]
    t = t.replace([np.inf, -np.inf], np.nan)
    return t


def burden_shares(raw: pd.DataFrame) -> pd.DataFrame:
    """Share of households in cohorts whose average burden exceeds 6% and 10%.

    This is approximate: it classifies whole cohorts by their average burden,
    which is the finest resolution LEAD offers.
    """
    cols = list(raw.columns)
    fip = next(c for c in cols if c.strip().upper() in ("FIP", "FIPS", "GEOID"))
    units = next(c for c in cols if c.strip().upper() == "UNITS")
    hh = pd.to_numeric(raw[units], errors="coerce").fillna(0)
    tot = {}
    for f in FIELDS:
        col, is_total = _find_col(cols, f)
        v = pd.to_numeric(raw[col], errors="coerce").fillna(0)
        tot[f] = v if is_total else v * hh
    with np.errstate(divide="ignore", invalid="ignore"):
        b = 100 * (tot["ELEP"] + tot["GASP"] + tot["FULP"]) / tot["HINCP"]
    # Cohorts with zero or negative income are treated as burdened, as in LEAD.
    b = b.where(tot["HINCP"] > 0, np.inf)
    g = pd.DataFrame({
        "GEOID": raw[fip].str.replace(r"\.0$", "", regex=True).str.zfill(11),
        "hh": hh,
        "hh_high": hh.where(b > C.BURDEN_HIGH, 0),
        "hh_severe": hh.where(b > C.BURDEN_SEVERE, 0),
    }).groupby("GEOID", as_index=False).sum()
    g["share_high"] = 100 * g["hh_high"] / g["hh"]
    g["share_severe"] = 100 * g["hh_severe"] / g["hh"]
    return g[["GEOID", "share_high", "share_severe"]]


def load(zip_path: Path) -> pd.DataFrame:
    raw = read_lead(zip_path)
    return tract_burden(raw).merge(burden_shares(raw), on="GEOID", how="left")
