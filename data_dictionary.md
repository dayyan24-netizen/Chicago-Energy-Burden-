# Data Dictionary: `data/processed/chicago_tracts.csv`

One row per Chicago census tract (2020 boundaries). The same columns, plus tract
geometry, are in `chicago_tracts.gpkg`.

## Identifiers
| Column | Description |
|---|---|
| `GEOID` | 11-digit census tract code (state 17 + county 031 + tract) |
| `land_sqmi` | Land area in square miles |

## Energy burden (DOE LEAD Tool, 2022 update)
| Column | Description |
|---|---|
| `households` | Number of households LEAD estimates for the tract |
| `burden` | **Main outcome.** Total annual energy costs / total household income x 100 |
| `burden_elec`, `burden_gas` | Same, using electricity or gas costs only |
| `energy_cost_avg` | Average annual energy cost per household ($) |
| `elec_cost_avg`, `gas_cost_avg` | Average annual electricity and gas cost per household ($) |
| `income_avg` | Average annual household income ($) |
| `share_high`, `share_severe` | Percent of households in income cohorts whose average burden is above 6% and 10% |
| `hincp_total`, `elep_total`, `gasp_total`, `fulp_total` | Tract totals of income, electricity, gas, and other fuel spending ($) |

## Explanatory variables (ACS 2018-2022 5-year)
Every percentage has a matching `_cv` column, its coefficient of variation
(standard error divided by the estimate). Values above 0.40 are generally
considered unreliable.

| Column | ACS table | Description |
|---|---|---|
| `median_hh_income` | B19013 | Median household income ($) |
| `ln_income` | B19013 | Natural log of median household income |
| `pct_black` | B03002 | Percent non-Hispanic Black |
| `pct_hispanic` | B03002 | Percent Hispanic or Latino (any race) |
| `pct_nh_white` | B03002 | Percent non-Hispanic white |
| `pct_renter` | B25003 | Percent of occupied units that are renter-occupied |
| `pct_pre1950` | B25034 | Percent of housing units built before 1950 |
| `median_year_built` | B25035 | Median year structure built |
| `pct_multifamily` | B25024 | Percent of units in buildings with 5 or more units |
| `pct_electric_heat` | B25040 | Percent of occupied units heated mainly with electricity |
| `pct_below_200fpl` | C17002 | Percent of people below 200% of the federal poverty level |

## Validation variables (ACS B25132, B25133)
| Column | Description |
|---|---|
| `acs_electricity_cost_annual`, `acs_gas_cost_annual` | Mean annual cost among households charged, estimated from bracket midpoints (top bracket = 1.25 x lower bound) |
| `acs_electricity_n_charged`, `acs_gas_n_charged` | Households counted in those brackets |

## Quality flags
| Column | Meaning |
|---|---|
| `flag_few_households` | Fewer than 100 households, so averages are unstable |
| `flag_no_burden` | LEAD has no burden estimate for the tract |
| `flag_unreliable_acs` | Income, renter share, or pre-1950 share has CV above 0.40 |
| `analysis_sample` | `True` if the tract is used in models (no household or missing-data problems) |

Spatial weights in `weights_queen.gal` and `weights_knn.gal` are built from the
analysis sample, in the row order listed in `weights_order.csv`.

---

# Stage 2 outputs: `data/processed/lisa_results.csv`

One row per tract in the analysis sample.

| Column | Description |
|---|---|
| `community_area` | Chicago community area containing the tract (from City of Chicago boundaries) |
| `burden_lisa_I` | Local Moran's I for energy burden; positive means the tract resembles its neighbors |
| `burden_lisa_p` | Two-sided permutation p-value (9,999 permutations) |
| `burden_cluster_fdr` | **Main cluster label.** High-High, Low-Low, High-Low, Low-High, or Not significant, at a 5% false discovery rate |
| `burden_cluster_p05` | Same label using an unadjusted p < 0.05 (for comparison only) |
| `share_severe_cluster_fdr` | Cluster label for the share of households above 10% burden |

Global results are in `reports/global_morans_i.csv` (Moran's I by variable and weights type).
