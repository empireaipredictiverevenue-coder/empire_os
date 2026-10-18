#!/usr/bin/env python3
"""Read-only bridge from existing Data Handler to three scoped Sales packages.

No CRM writes, email sends, buyer creations, marketplace posts, payments,
customer file delivery or public website changes.
"""
from __future__ import annotations
import argparse
import json
from typing import Any

from empire_os.data_brokerage_monetization_portfolio import (
    build_monetization_portfolio,
)
from empire_os.data_brokerage_sales_activation import (
    build_sales_activation_review,validate_sales_activation_review,
)
from scripts.preview_data_brokerage_monetization import source_catalog
from scripts.review_data_brokerage_first_sale_closeout_20261018 import (
    inspect as inspect_first_sale,
)

def review(*,show_packages:bool=False)->dict[str,Any]:
    try:
        source=source_catalog()
        portfolio=build_monetization_portfolio(source)
        receipt=inspect_first_sale()
        result=build_sales_activation_review(portfolio,receipt)
        if not validate_sales_activation_review(result):
            raise ValueError("REVENUE_AUTHORITY_UNVERIFIED")
        if show_packages:
            return result
        return {
            "schema_version":result["schema_version"],
            "status":result["status"],
            "mode":"OBSERVE",
            "existing_product_families":result["source_product_families"],
            "registered_hypotheses":result["catalog_offer_hypotheses"],
            "draft_packages":result["draft_package_count"],
            "draft_offer_codes":[x["offer_code"] for x in result["packages"]],
            "sequence":result["recommended_sequence"],
            "buyer_acceptance_verified":False,
            "source_resale_authorized":False,
            "commercial_outbound_authorized":False,
            "new_contracts_executed":False,
            "payment_or_revenue_verified":False,
            "crm_mutation":False,"database_writes":False,
            "external_marketplace_registered":False,
            "execution_authority":"NONE",
        }
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        return {
            "schema_version":"empire.data_brokerage.sales_activation_review.v1",
            "status":"HOLD_SOURCE_EVIDENCE_OR_COMMERCIAL_AUTHORITY",
            "mode":"OBSERVE","execution_authority":"NONE",
            "outbound_sent":False,"crm_mutation":False,
            "payment_activated":False,"database_writes":False
        }

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    parser.add_argument("--show-packages",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_FLAG_REQUIRED"}))
        return 2
    r=review(show_packages=args.show_packages)
    print(json.dumps(r,sort_keys=True,allow_nan=False))
    return 0 if r["status"]=="THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD" else 2

if __name__=="__main__":
    raise SystemExit(main())
