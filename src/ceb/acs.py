"""Build tract-level explanatory variables from American Community Survey data.

Shares are computed with their margins of error, following the Census Bureau's
formula for derived proportions, so unreliable estimates can be flagged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

Z90 = 1.645  # ACS margins of error are 90% intervals


# ---------------------------------------------------------------- parsing
def _to_frame(rows: list[list[str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"]
    return df.drop(columns=["state", "county", "tract"]).set_index("GEOID")


def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.apply(pd.to_numeric, errors="coerce")
    # The Census API uses large negative codes (e.g. -666666666) for "not available".
    return out.mask(out <= -555555555)


def read_covariates(path: Path) -> pd.DataFrame:
    payload = json.loads(Path(path).read_text())
    frames = [_to_frame(rows) for rows in payload["chunks"]]
    raw = _numeric(pd.concat(frames, axis=1))
    rename = {}
    for code, name in C.ACS_VARS.items():
        rename[code + "E"] = name
        rename[code + "M"] = name + "_moe"
    return raw.rename(columns=rename)


# ---------------------------------------------------------------- derived shares
def _sum(df, names):
    est = df[names].sum(axis=1, min_count=1)
    moe = np.sqrt((df[[n + "_moe" for n in names]] ** 2).sum(axis=1, min_count=1))
    return est, moe


def share(num, num_moe, den, den_moe):
    """Proportion (as percent) and its MOE, per Census Bureau guidance.

    If the term under the square root is negative, the ratio formula is used.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        p = num / den
        under = num_moe ** 2 - (p ** 2) * den_moe ** 2
        ratio = num_moe ** 2 + (p ** 2) * den_moe ** 2
        moe = np.sqrt(np.where(under >= 0, under, ratio)) / den
    return 100 * p, 100 * moe


def cv(est, moe):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (moe / Z90) / est.abs()


def build_covariates(acs: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=acs.index)
    out["median_hh_income"] = acs["median_hh_income"]
    out["median_hh_income_cv"] = cv(acs["median_hh_income"], acs["median_hh_income_moe"])
    out["ln_income"] = np.log(acs["median_hh_income"].where(acs["median_hh_income"] > 0))
    out["pop_total"] = acs["pop_total"]
    out["occ_units"] = acs["occ_units"]
    out["median_year_built"] = acs["median_year_built"]

    def add(name, num_names, den_name):
        n, nm = _sum(acs, num_names)
        out[name], moe = share(n, nm, acs[den_name], acs[den_name + "_moe"])
        out[name + "_cv"] = cv(out[name], moe)

    add("pct_black", ["pop_nh_black"], "pop_total")
    add("pct_hispanic", ["pop_hispanic"], "pop_total")
    add("pct_nh_white", ["pop_nh_white"], "pop_total")
    add("pct_renter", ["renter_units"], "occ_units")
    add("pct_pre1950", ["units_built_1940s", "units_built_pre1940"], "units_yb_total")
    add("pct_multifamily", ["units_5to9", "units_10to19", "units_20to49", "units_50plus"], "units_bld_total")
    add("pct_electric_heat", ["heat_electric"], "heat_total")
    add("pct_below_200fpl", ["pov_lt050", "pov_050_099", "pov_100_124",
                             "pov_125_149", "pov_150_184", "pov_185_199"], "pov_universe")
    return out


# ---------------------------------------------------------------- cost brackets
_RANGE = re.compile(r"\$([\d,]+)\s+to\s+\$([\d,]+)")
_LESS = re.compile(r"less than \$([\d,]+)", re.I)
_MORE = re.compile(r"\$([\d,]+)\s+or more", re.I)


def bracket_midpoint(label: str) -> float | None:
    """Dollar midpoint for an ACS cost bracket label; None if not a bracket.

    The open-ended top bracket is set to 1.25 x its lower bound, a common
    convention that we test in robustness checks.
    """
    leaf = label.split("!!")[-1]
    if m := _RANGE.search(leaf):
        lo, hi = (float(x.replace(",", "")) for x in m.groups())
        return (lo + hi + 1) / 2
    if m := _LESS.search(leaf):
        return float(m.group(1).replace(",", "")) / 2
    if m := _MORE.search(leaf):
        return 1.25 * float(m.group(1).replace(",", ""))
    return None


def cost_index(path: Path) -> pd.DataFrame:
    """Estimated mean annual electricity and gas cost among households charged.

    Built from ACS tables B25132 and B25133, which count households by monthly
    cost bracket. This is an independent check on LEAD, not a replacement.
    """
    payload = json.loads(Path(path).read_text())
    out = []
    for group, fuel in C.ACS_COST_GROUPS.items():
        df = _numeric(_to_frame(payload[group]["data"]).filter(regex=r"_\d{3}E$"))
        labels = payload[group]["labels"]["variables"]
        mids = {v: bracket_midpoint(labels[v]["label"]) for v in df.columns if v in labels}
        mids = {v: m for v, m in mids.items() if m is not None}
        counts = df[list(mids)]
        n = counts.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            monthly = (counts * pd.Series(mids)).sum(axis=1) / n
        out.append(pd.DataFrame({f"acs_{fuel}_cost_annual": 12 * monthly,
                                 f"acs_{fuel}_n_charged": n}))
    return pd.concat(out, axis=1)
