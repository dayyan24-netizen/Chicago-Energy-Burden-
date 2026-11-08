"""Run the project pipeline.

    python run_pipeline.py              # all stages
    python run_pipeline.py --stage 1    # data build only
    python run_pipeline.py --stage 2    # spatial analysis only (needs Stage 1 outputs)
    python run_pipeline.py --force      # re-download raw files
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ceb import build, download, explore  # noqa: E402


def stage1(force=False):
    print("== Stage 1: data build ==")
    lead_zip = download.download_lead(force)
    tract_zip, place_zip = download.download_tiger(force)
    cov_json, cost_json = download.download_acs(force)
    build.run(tract_zip, place_zip, lead_zip, cov_json, cost_json)


def stage2(force=False):
    print("== Stage 2: exploratory spatial analysis ==")
    explore.run(download.download_community_areas(force))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", type=int, choices=[1, 2], help="run one stage only")
    ap.add_argument("--force", action="store_true", help="re-download raw files")
    args = ap.parse_args()
    if args.stage in (None, 1):
        stage1(args.force)
    if args.stage in (None, 2):
        stage2(args.force)


if __name__ == "__main__":
    main()
