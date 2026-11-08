"""Download raw data files. Each download is skipped if the file already exists."""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from . import config as C

TIMEOUT = 120


def _fetch(url: str, dest: Path, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print(f"  already have {dest.name}")
        return dest
    print(f"  downloading {url}")
    with requests.get(url, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(dest)
    return dest


def download_lead(force: bool = False) -> Path:
    return _fetch(C.LEAD_ZIP_URL, C.RAW / "lead" / Path(C.LEAD_ZIP_URL).name, force)


def download_tiger(force: bool = False) -> tuple[Path, Path]:
    tracts = _fetch(C.TIGER_TRACT_URL, C.RAW / "tiger" / Path(C.TIGER_TRACT_URL).name, force)
    places = _fetch(C.TIGER_PLACE_URL, C.RAW / "tiger" / Path(C.TIGER_PLACE_URL).name, force)
    return tracts, places


def _census_get(params: dict) -> list[list[str]]:
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params = {**params, "key": key}
    r = requests.get(C.ACS_API, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def download_acs(force: bool = False) -> tuple[Path, Path]:
    """Save ACS tract data for Cook County as raw Census API JSON.

    Returns (covariates_json, cost_brackets_json).
    """
    out_cov = C.RAW / "acs" / f"acs{C.ACS_YEAR}_covariates.json"
    out_cost = C.RAW / "acs" / f"acs{C.ACS_YEAR}_cost_brackets.json"
    out_cov.parent.mkdir(parents=True, exist_ok=True)
    geo = {"for": "tract:*", "in": [f"state:{C.STATE_FIPS}", f"county:{C.COUNTY_FIPS}"]}

    if force or not out_cov.exists():
        print("  requesting ACS covariates from the Census API")
        names = []
        for v in C.ACS_VARS:
            names += [v + "E", v + "M"]
        # The API allows 50 variables per call, so request in chunks.
        # Chunks are joined later on the tract ID, not on row order.
        chunks = [_census_get({"get": ",".join(names[i:i + 48]), **geo})
                  for i in range(0, len(names), 48)]
        out_cov.write_text(json.dumps({"chunks": chunks}))
    else:
        print(f"  already have {out_cov.name}")

    if force or not out_cost.exists():
        print("  requesting ACS electricity and gas cost brackets")
        payload = {}
        for group in C.ACS_COST_GROUPS:
            payload[group] = {
                "data": _census_get({"get": f"group({group})", **geo}),
                "labels": requests.get(f"{C.ACS_API}/groups/{group}.json", timeout=TIMEOUT).json(),
            }
        out_cost.write_text(json.dumps(payload))
    else:
        print(f"  already have {out_cost.name}")
    return out_cov, out_cost


def download_community_areas(force: bool = False) -> Path | None:
    """Chicago's 77 community areas, used to label tracts. Optional: returns None on failure."""
    dest = C.RAW / "chicago" / "community_areas.geojson"
    if dest.exists() and not force:
        print(f"  already have {dest.name}")
        return dest
    for url in C.COMMUNITY_AREAS_URLS:
        try:
            return _fetch(url, dest, force=True)
        except requests.RequestException as e:
            print(f"  could not download community areas from {url}: {e}")
    print("  continuing without community area labels")
    return None


def download_all(force: bool = False) -> None:
    print("LEAD Tool")
    download_lead(force)
    print("TIGER/Line boundaries")
    download_tiger(force)
    print("American Community Survey")
    download_acs(force)
