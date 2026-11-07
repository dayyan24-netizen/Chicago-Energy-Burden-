# Chicago Energy Burden

**A spatial analysis of household energy burden and inequality across Chicago's census tracts.**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/dayyan24-netizen/Chicago-Energy-Burden/blob/main/notebooks/01_data_build.ipynb)

Energy burden is the share of a household's income that goes to home energy bills.
Across the Chicago metro area, the typical household spends about 2.7% of its income
on energy, while the typical low-income household spends 8.0% (ACEEE, 2020). This
project asks where in the city that burden falls and why:

1. **Where is burden concentrated?** Is it spatially clustered, and where are the significant hotspots?
2. **What explains it?** How are income, racial composition, housing age, housing type, and renting associated with burden once spatial dependence is accounted for?
3. **High bills or low incomes?** Do neighborhood gaps come mainly from higher energy costs or lower incomes?
4. **Does it differ across the city?** Are these relationships stronger in some areas than others?

This is a James Rocco Data Research Scholarship project at Lake Forest College,
advised by Dr. Andrew Gard and Dr. Sugata Banerji.

## Project status

| Stage | Status |
|---|---|
| 1. Data pipeline: download, clean, validate | Done |
| 2. Exploratory spatial analysis: maps, Moran's I, LISA clusters | Next |
| 3. Regression: OLS, spatial lag/error, MGWR | Planned |
| 4. Robustness checks | Planned |
| 5. Interactive web map and policy brief | Planned |

## Data

| Source | What it provides |
|---|---|
| [DOE LEAD Tool, 2022 update](https://doi.org/10.25984/2504170) | Tract-level household income and energy costs, calibrated to utility data |
| [ACS 5-year estimates, 2018-2022](https://www.census.gov/data/developers/data-sets/acs-5year.html) | Income, race and ethnicity, housing age and type, tenure, heating fuel, with margins of error |
| [TIGER/Line 2022](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | Census tract and City of Chicago boundaries |
| [ACEEE Chicago energy burden fact sheet](https://www.aceee.org/sites/default/files/pdfs/aceee-01_energy_burden_-_chicago.pdf) | Published benchmarks used to validate the burden measure |

All data are public. Raw downloads are not stored in the repository; the pipeline
fetches them.

## How it works

```
run_pipeline.py
   |
   |-- download.py   LEAD zip, TIGER boundaries, ACS tables (skips files already downloaded)
   |-- geo.py        keeps Cook County tracts whose interior point is inside Chicago
   |-- lead.py       adds LEAD income cohorts back up to tract totals -> energy burden
   |-- acs.py        builds percentages with Census-formula margins of error
   |-- build.py      merges everything, flags unreliable tracts, writes weights and a validation report
```

**Energy burden** for each tract is total household energy spending divided by
total household income. This is the "average household" burden used by DOE and by
Moore and Webb (2022). The pipeline checks the result against ACEEE's published
Chicago figures and against an independent estimate from ACS cost brackets, and
warns if the numbers point to a units problem.

## Run it

**Easiest: Google Colab (nothing to install).** Click the *Open in Colab* badge
above, then choose **Runtime > Run all**. The notebook downloads the data, runs the
pipeline, and shows the validation report and first map.

**On your own computer:**

```bash
git clone https://github.com/dayyan24-netizen/Chicago-Energy-Burden.git
cd Chicago-Energy-Burden
pip install -r requirements.txt
python run_pipeline.py
```

A free [Census API key](https://api.census.gov/data/key_signup.html) is optional; if
you have one, set it as the `CENSUS_API_KEY` environment variable.

## Outputs

| File | Contents |
|---|---|
| `data/processed/chicago_tracts.gpkg` | Analysis dataset with tract boundaries (open in Python, QGIS, or ArcGIS) |
| `data/processed/chicago_tracts.csv` | Same data without geometry |
| `data/processed/weights_queen.gal`, `weights_knn.gal` | Spatial weights matrices |
| `reports/validation_report.md` | Coverage, benchmark checks, top-burden tracts, and map |
| `docs/data_dictionary.md` | Every column explained |

## Tests

The test suite runs the whole pipeline on synthetic data shaped like the real files,
so it works offline:

```bash
python -m pytest
```

## Repository layout

```
Chicago-Energy-Burden/
|-- run_pipeline.py        one command to rebuild everything
|-- src/ceb/               pipeline code
|-- notebooks/             step-by-step walkthroughs (Colab-ready)
|-- tests/                 automated tests with synthetic data
|-- data/processed/        analysis-ready outputs
|-- reports/               validation report and figures
`-- docs/                  data dictionary
```

## References

- ACEEE. (2020). *Energy burdens in Chicago* [Fact sheet].
- Ma, O., & Vimont, A. (2024). *Low-Income Energy Affordability Data (LEAD) Tool: 2022 update* [Data set]. U.S. DOE. https://doi.org/10.25984/2504170
- Moore, D., & Webb, A. L. (2022). Evaluating energy burden at the urban scale: A spatial regression approach in Cincinnati, Ohio. *Energy Policy, 160*, 112651.
- Rey, S. J., & Anselin, L. (2007). PySAL: A Python library of spatial analytical methods. *The Review of Regional Studies, 37*(1), 5-27.

## Author

**Dayyan Fundi**, Economics and Data Science, Lake Forest College (Class of 2028)

Released under the MIT License.
