"""Inspect new official source packs; run one bounded dental API pilot or local CSLB file.

NPPES API queries must be narrow and manually approved; bulk use requires
CMS's official DDS file. SRA/FCA key-restricted and US insurer/legal lookups
remain manual. No canonical DB, emails, public raw data or trading.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.official_vertical_source_packs import SOURCES, assess_source_access
from empire_os.nppes_dental_source import sweep_nppes_dental
from empire_os.cslb_contractor_csv_source import review_cslb_file
from empire_os.nyc_contractors_official_source import sweep_nyc_companies


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--run-founder-approved", action="store_true")
    p.add_argument("--source", default="catalog",
                   choices=["catalog", "us_cms_nppes_dental_npi2",
                            "us_cslb_official_contractor_csv",
                            "us_nyc_dcwp_home_improvement_companies"])
    p.add_argument("--city", default="Dallas")
    p.add_argument("--state", default="TX")
    p.add_argument("--private-root", type=Path,
        default=Path("/srv/empire_os/runtime/lead_supply/private_us_dental_orgs"))
    p.add_argument("--official-csv-file", type=Path)
    p.add_argument("--source-document-ref")
    p.add_argument("--rights-review-ref")
    args = p.parse_args(argv)
    try:
        if args.source == "catalog":
            if not args.read_only:
                p.error("--read-only required for catalog")
            result = {
                "mode": "OFFICIAL_SOURCE_READINESS_REVIEW",
                "sources": [assess_source_access(x.source_id) for x in SOURCES],
                "canonical_empiredb_writes": False,
                "outbound_authorized": False,
            }
        elif args.source == "us_cms_nppes_dental_npi2":
            if not args.run_founder_approved:
                p.error("--run-founder-approved required for bounded NPPES pilot")
            result = sweep_nppes_dental(
                args.private_root, city=args.city, state=args.state
            )
        elif args.source == "us_nyc_dcwp_home_improvement_companies":
            if not args.run_founder_approved:
                p.error("--run-founder-approved required for bounded NYC pilot")
            result = sweep_nyc_companies(
                Path("/srv/empire_os/runtime/lead_supply/private_nyc_contractors")
            )
        else:
            if not args.read_only:
                p.error("--read-only required for offline CSLB data parsing")
            if not args.official_csv_file or not args.source_document_ref or not args.rights_review_ref:
                p.error("official CSLB CSV and independently reviewed download/rights refs required")
            result = review_cslb_file(
                args.official_csv_file,
                source_document_ref=args.source_document_ref,
                rights_review_ref=args.rights_review_ref,
                private_output=args.private_root / "cslb_private_observations.json",
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, UnicodeError) as e:
        print(json.dumps({
            "mode": "OFFICIAL_SOURCE_READINESS_REVIEW", "state": "HOLD",
            "reason_class": type(e).__name__, "canonical_empiredb_writes": False,
            "outbound_authorized": False, "execution_authority": "none",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
