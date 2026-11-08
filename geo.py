"""Chicago tract boundaries and spatial weights."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import libpysal

from . import config as C


def chicago_tracts(tract_zip: Path, place_zip: Path) -> gpd.GeoDataFrame:
    """Cook County tracts whose interior point falls inside the City of Chicago.

    Using an interior point (not overlap) assigns each tract to exactly one
    place, so tracts that only touch the city limit are left out.
    """
    tracts = gpd.read_file(tract_zip)
    tracts = tracts[tracts["COUNTYFP"] == C.COUNTY_FIPS].to_crs(C.CRS_PROJECTED)
    places = gpd.read_file(place_zip).to_crs(C.CRS_PROJECTED)
    city = places[places["GEOID"] == C.CHICAGO_PLACE_FIPS]
    if city.empty:
        raise ValueError("Chicago (place 1714000) not found in the TIGER place file")
    pts = tracts.copy()
    pts["geometry"] = tracts.representative_point()
    inside = gpd.sjoin(pts, city[["geometry"]], predicate="within", how="inner").index
    out = tracts.loc[inside, ["GEOID", "ALAND", "AWATER", "geometry"]].copy()
    out["land_sqmi"] = out["ALAND"] / 2_589_988.11
    return out.drop(columns=["ALAND", "AWATER"]).reset_index(drop=True)


def weights(gdf: gpd.GeoDataFrame, kind: str = "queen", k: int = 6):
    """Row-standardized spatial weights.

    kind = "queen" (shared edge or corner) or "knn" (k nearest centroids).
    Islands with no queen neighbor are reported so they can be handled.
    """
    ids = gdf["GEOID"].tolist()
    if kind == "queen":
        w = libpysal.weights.Queen.from_dataframe(gdf, ids=ids, use_index=False)
    elif kind == "knn":
        w = libpysal.weights.KNN.from_dataframe(gdf, k=k, ids=ids, use_index=False)
    else:
        raise ValueError(kind)
    if w.id_order != ids:
        raise RuntimeError("Spatial weights are not in the same order as the tracts")
    w.transform = "r"
    return w
