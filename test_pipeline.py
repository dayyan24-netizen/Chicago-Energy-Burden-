import numpy as np
import pandas as pd
import pytest

from ceb import acs, build, config as C, lead


# ---------------------------------------------------------------- LEAD
def test_lead_totals_and_averages_give_same_burden():
    totals = pd.DataFrame({"FIP": ["17031010100"] * 2, "UNITS": ["100", "300"],
                           "HINCP*UNITS": ["2000000", "24000000"], "ELEP*UNITS": ["100000", "300000"],
                           "GASP*UNITS": ["80000", "240000"], "FULP*UNITS": ["0", "0"]})
    avgs = pd.DataFrame({"fip": ["17031010100"] * 2, "units": ["100", "300"],
                         "hincp": ["20000", "80000"], "elep": ["1000", "1000"],
                         "gasp": ["800", "800"], "fulp": ["0", "0"]})
    a, b = lead.tract_burden(totals), lead.tract_burden(avgs.rename(columns=str.upper))
    expected = 100 * (400000 + 320000) / 26000000
    assert a["burden"].iloc[0] == pytest.approx(expected)
    assert b["burden"].iloc[0] == pytest.approx(expected)
    assert a["households"].iloc[0] == 400


def test_lead_shares_count_burdened_cohorts():
    raw = pd.DataFrame({"FIP": ["17031010100"] * 2, "UNITS": ["100", "300"],
                        "HINCP*UNITS": ["1000000", "30000000"], "ELEP*UNITS": ["100000", "300000"],
                        "GASP*UNITS": ["0", "0"], "FULP*UNITS": ["0", "0"]})
    s = lead.burden_shares(raw).iloc[0]
    assert s["share_high"] == pytest.approx(25.0)   # first cohort is at 10%, second at 1%
    assert s["share_severe"] == pytest.approx(0.0)  # 10% is not *above* 10%


def test_lead_missing_column_gives_clear_error():
    with pytest.raises(KeyError, match="GASP"):
        lead.tract_burden(pd.DataFrame({"FIP": ["1"], "UNITS": ["1"], "HINCP*UNITS": ["1"],
                                        "ELEP*UNITS": ["1"], "FULP*UNITS": ["1"]}))


# ---------------------------------------------------------------- ACS
@pytest.mark.parametrize("label,mid", [
    ("Estimate!!Total:!!Charged:!!Less than $50", 25),
    ("Estimate!!Total:!!Charged:!!$50 to $99", 75),
    ("Estimate!!Total:!!Charged:!!$1,000 to $1,499", 1250),
    ("Estimate!!Total:!!Charged:!!$250 or more", 312.5),
    ("Estimate!!Total:!!Charged for electricity:", None),
])
def test_bracket_midpoints(label, mid):
    assert acs.bracket_midpoint(label) == mid


def test_share_moe_matches_census_formula():
    p, moe = acs.share(pd.Series([200.0]), pd.Series([40.0]), pd.Series([1000.0]), pd.Series([60.0]))
    assert p.iloc[0] == pytest.approx(20.0)
    assert moe[0] == pytest.approx(100 * np.sqrt(40**2 - 0.2**2 * 60**2) / 1000)


# ---------------------------------------------------------------- end to end
def test_full_build(fake_data):
    df = build.run(**fake_data)
    assert len(df) == 16                                   # inner 4 x 4 grid is Chicago
    assert df["GEOID"].str.len().eq(11).all()
    assert df["burden"].between(0.5, 20).all()
    assert df["flag_few_households"].sum() == 0            # tiny tract is outside the city
    assert {"pct_black", "pct_pre1950", "ln_income", "share_high",
            "acs_electricity_cost_annual"} <= set(df.columns)
    assert (C.PROCESSED / "chicago_tracts.gpkg").exists()
    assert (C.PROCESSED / "weights_queen.gal").exists()
    report = (C.REPORTS / "validation_report.md").read_text()
    assert "Citywide burden" in report and "—" not in report
    assert (C.REPORTS / "figures" / "burden_map.png").exists()


def test_unit_check_flags_monthly_costs():
    assert build.unit_check(0.2) is not None
    assert build.unit_check(2.5) is None
