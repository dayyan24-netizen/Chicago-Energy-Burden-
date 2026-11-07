"""Run the full data build: download raw data, then build the tract dataset.

    python run_pipeline.py            # download anything missing, then build
    python run_pipeline.py --force    # re-download everything
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ceb import build, download  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-download raw files")
    args = ap.parse_args()

    lead_zip = download.download_lead(args.force)
    tract_zip, place_zip = download.download_tiger(args.force)
    cov_json, cost_json = download.download_acs(args.force)
    build.run(tract_zip, place_zip, lead_zip, cov_json, cost_json)


if __name__ == "__main__":
    main()
