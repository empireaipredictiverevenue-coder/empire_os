"""Observe all SKU prices and feature-category competitor benchmarks, no writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_catalogue_price_comparison import (
    SCHEMA, CataloguePricingHold, review_catalogue_price_comparison,
)
from empire_os.predictive_catalog_readiness_bridge import (
    ROOT_CATALOGUE, MAX_CLOCK_SKEW_SECONDS,
    ProductContractHold, _read_bounded_file, _review_catalogue, _stamp,
)
from empire_os.predictive_comparison_gap_report import (
    build_comparison_gap_report,
)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--all-products", action="store_true")
    mode.add_argument("--gaps", action="store_true")
    mode.add_argument("--product-code")
    args=parser.parse_args(argv)
    try:
        now=datetime.now(timezone.utc)
        catalogue, digest, mtime=_read_bounded_file(ROOT_CATALOGUE, owner_uid=0)
        admitted=_review_catalogue(catalogue, as_of=now)
        if abs((_stamp(catalogue["generated_at"])-mtime).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
            raise ProductContractHold("original catalogue timestamp discrepancy")
        report=review_catalogue_price_comparison(catalogue)
        assert admitted["catalogue_product_count"] == report["catalogue_product_count"]
        report["source_root_owned_snapshot_custody_verified"]=True
        report["source_original_empiredb_issuer_authenticated"]=False
        report["original_catalogue_sha256_change_detection_only"]=digest
        report["source_age_seconds"]=admitted["catalogue_age_seconds"]
        if args.gaps:
            gaps=build_comparison_gap_report(report)
            gaps["source_root_owned_snapshot_custody_verified"]=True
            gaps["source_original_empiredb_issuer_authenticated"]=False
            gaps["original_catalogue_sha256_change_detection_only"]=digest
            gaps["source_age_seconds"]=admitted["catalogue_age_seconds"]
            report=gaps
        elif args.product_code is not None:
            if (len(args.product_code)>90 or
                    not all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in args.product_code)):
                raise CataloguePricingHold("invalid original SKU identity")
            matches=[row for row in report["products"]
                     if row["product_code"]==args.product_code]
            if len(matches)!=1:
                raise CataloguePricingHold("original SKU is not in catalogue")
            report["products"]=matches
            report["selected_product_code"]=args.product_code
            report["selected_product_read_only"]=True
        elif not args.all_products:
            report.pop("products")
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    except (CataloguePricingHold, ProductContractHold, ValueError, TypeError, OSError, KeyError, AssertionError):
        print(json.dumps({
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"COMPARISON_ORIGINAL_CATALOGUE_SOURCE_HELD",
            "catalogue_product_count":None,
            "source_root_owned_snapshot_custody_verified":False,
            "source_original_empiredb_issuer_authenticated":False,
            "customer_price_change_authorized":False,
            "astra_gpt6_independent_review":"NOT_EXECUTED",
            "database_writes":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
