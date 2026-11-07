"""Project settings: data years, source URLs, file paths, and published benchmarks.

Everything that might change between runs (a newer LEAD release, a different ACS
year) lives here so the rest of the code never hard-codes it.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "reports"

# ---------------------------------------------------------------- geography
STATE_FIPS = "17"          # Illinois
COUNTY_FIPS = "031"        # Cook County
CHICAGO_PLACE_FIPS = "1714000"
CRS_PROJECTED = 26916      # NAD83 / UTM zone 16N, meters (good for Chicago distances)

# ---------------------------------------------------------------- data years
# LEAD 2022 update is built from 2018-2022 ACS microdata, so covariates use the
# matching 2018-2022 5-year ACS. The 2020-2024 release is used as a later check.
LEAD_YEAR = 2022
ACS_YEAR = 2022            # end year of the 5-year window (2018-2022)
TIGER_YEAR = 2022          # 2020-vintage tract boundaries

# ---------------------------------------------------------------- source URLs
LEAD_ZIP_URL = f"https://data.openei.org/files/6219/IL-{LEAD_YEAR}-LEAD-data.zip"
TIGER_TRACT_URL = (f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/TRACT/"
                   f"tl_{TIGER_YEAR}_{STATE_FIPS}_tract.zip")
TIGER_PLACE_URL = (f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/PLACE/"
                   f"tl_{TIGER_YEAR}_{STATE_FIPS}_place.zip")
ACS_API = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

# ---------------------------------------------------------------- ACS variables
# Estimates (E) and margins of error (M) are both requested.
ACS_VARS = {
    "B19013_001": "median_hh_income",
    "B03002_001": "pop_total",
    "B03002_003": "pop_nh_white",
    "B03002_004": "pop_nh_black",
    "B03002_012": "pop_hispanic",
    "B25003_001": "occ_units",
    "B25003_003": "renter_units",
    "B25034_001": "units_yb_total",
    "B25034_010": "units_built_1940s",
    "B25034_011": "units_built_pre1940",
    "B25035_001": "median_year_built",
    "B25024_001": "units_bld_total",
    "B25024_006": "units_5to9",
    "B25024_007": "units_10to19",
    "B25024_008": "units_20to49",
    "B25024_009": "units_50plus",
    "B25040_001": "heat_total",
    "B25040_002": "heat_utility_gas",
    "B25040_004": "heat_electric",
    "C17002_001": "pov_universe",
    "C17002_002": "pov_lt050",
    "C17002_003": "pov_050_099",
    "C17002_004": "pov_100_124",
    "C17002_005": "pov_125_149",
    "C17002_006": "pov_150_184",
    "C17002_007": "pov_185_199",
}
ACS_COST_GROUPS = {"B25132": "electricity", "B25133": "gas"}  # monthly cost brackets

# ---------------------------------------------------------------- quality rules
MIN_HOUSEHOLDS = 100       # tracts with fewer households are flagged as unstable
CV_UNRELIABLE = 0.40       # coefficient of variation above this is flagged
BURDEN_HIGH = 6.0          # percent of income
BURDEN_SEVERE = 10.0

# ---------------------------------------------------------------- benchmarks
# Published Chicago figures used to sanity-check our burden measure.
ACEEE_BENCHMARKS = {
    "aceee_2020_median_all": 2.7,        # ACEEE (2020) Chicago fact sheet, metro area
    "aceee_2020_median_low_income": 8.0,
    "aceee_2024_median_all": 2.2,        # ACEEE (2024) city data update, 2021 AHS
    "aceee_2024_median_low_income": 7.2,
}
