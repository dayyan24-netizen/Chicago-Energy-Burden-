"""Synthetic fixtures shaped like the real downloads, so the pipeline can be
tested without network access. Values are random but realistic in range."""
import io
import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ceb import config as C  # noqa: E402

N = 6  # 6 x 6 grid of fake tracts; the inner 4 x 4 are "in Chicago"
rng = np.random.default_rng(42)


def _geoids():
    return [f"17031{100 + i:04d}00" for i in range(N * N)]


def _zip_shapefile(gdf, path, stem):
    tmp = path.parent / stem
    tmp.mkdir(exist_ok=True)
    gdf.to_file(tmp / f"{stem}.shp")
    with zipfile.ZipFile(path, "w") as z:
        for f in tmp.iterdir():
            z.write(f, f.name)


@pytest.fixture
def fake_data(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(C, "REPORTS", tmp_path / "reports")
    geoids = _geoids()

    # Tracts: a grid near downtown Chicago, in NAD83 lon/lat like TIGER files
    x0, y0, d = -87.75, 41.80, 0.02
    polys = [box(x0 + (i % N) * d, y0 + (i // N) * d, x0 + (i % N + 1) * d, y0 + (i // N + 1) * d)
             for i in range(N * N)]
    tracts = gpd.GeoDataFrame({"GEOID": geoids, "COUNTYFP": "031",
                               "ALAND": 2_000_000, "AWATER": 0}, geometry=polys, crs=4269)
    tract_zip = tmp_path / "tl_2022_17_tract.zip"
    _zip_shapefile(tracts, tract_zip, "tl_2022_17_tract")

    city = box(x0 + d, y0 + d, x0 + (N - 1) * d, y0 + (N - 1) * d)
    places = gpd.GeoDataFrame({"GEOID": [C.CHICAGO_PLACE_FIPS, "1700000"]},
                              geometry=[city, box(-88.5, 41, -88.4, 41.1)], crs=4269)
    place_zip = tmp_path / "tl_2022_17_place.zip"
    _zip_shapefile(places, place_zip, "tl_2022_17_place")

    # LEAD: three income cohorts per tract, totals in "*UNITS" columns
    rows = []
    for g in geoids:
        for bracket, inc in (("0-30%", 14000), ("30-80%", 42000), ("80%+", 110000)):
            units = int(rng.integers(50, 600))
            elec, gas = rng.normal(1100, 150), rng.normal(850, 120)
            rows.append({"FIP": int(g), "TEN": "RENTER", "AMI68": bracket, "UNITS": units,
                         "HINCP*UNITS": inc * units, "ELEP*UNITS": elec * units,
                         "GASP*UNITS": gas * units, "FULP*UNITS": 5 * units})
    rows[0]["UNITS"] = 10; rows[1]["UNITS"] = 10; rows[2]["UNITS"] = 10  # one tiny tract
    lead_csv = pd.DataFrame(rows).to_csv(index=False)
    lead_zip = tmp_path / "IL-2022-LEAD-data.zip"
    with zipfile.ZipFile(lead_zip, "w") as z:
        z.writestr("IL-2022-LEAD-data/IL AMI Census Tracts 2022.csv", lead_csv)
        z.writestr("IL-2022-LEAD-data/IL FPL Counties 2022.csv", "FIP,UNITS\n17031,1\n")

    # ACS covariates, split into API-sized chunks like the real download
    names = []
    for v in C.ACS_VARS:
        names += [v + "E", v + "M"]
    def val(n):
        if n.endswith("M"):
            return str(int(rng.integers(20, 150)))
        if n.startswith("B19013"):
            return str(int(rng.integers(20000, 140000)))
        if n.startswith("B25035"):
            return str(int(rng.integers(1925, 1980)))
        if n.endswith("_001E"):
            return str(int(rng.integers(1500, 3000)))
        return str(int(rng.integers(50, 600)))
    chunks = []
    for i in range(0, len(names), 48):
        part = names[i:i + 48]
        header = part + ["state", "county", "tract"]
        body = [[val(n) for n in part] + ["17", "031", g[5:]] for g in geoids]
        body[3][0] = "-666666666"  # Census "not available" code
        chunks.append([header] + body)
    cov_json = tmp_path / "acs_cov.json"
    cov_json.write_text(json.dumps({"chunks": chunks}))

    # ACS cost brackets with real-style labels
    def group(code, brackets):
        labels = {"variables": {f"{code}_001E": {"label": "Estimate!!Total:"},
                                f"{code}_002E": {"label": "Estimate!!Total:!!Charged for it:"}}}
        for j, b in enumerate(brackets, start=3):
            labels["variables"][f"{code}_{j:03d}E"] = {"label": f"Estimate!!Total:!!Charged for it:!!{b}"}
        labels["variables"][f"{code}_{len(brackets) + 3:03d}E"] = {"label": "Estimate!!Total:!!Not charged"}
        cols = [f"{code}_{j:03d}E" for j in range(1, len(brackets) + 4)]
        data = [cols + ["state", "county", "tract"]]
        for g in geoids:
            data.append([str(int(rng.integers(0, 300))) for _ in cols] + ["17", "031", g[5:]])
        return {"data": data, "labels": labels}
    br = ["Less than $50", "$50 to $99", "$100 to $149", "$150 to $199", "$200 or more"]
    cost_json = tmp_path / "acs_cost.json"
    cost_json.write_text(json.dumps({"B25132": group("B25132", br), "B25133": group("B25133", br)}))

    return dict(tract_zip=tract_zip, place_zip=place_zip, lead_zip=lead_zip,
                acs_cov_json=cov_json, acs_cost_json=cost_json)
