#!/usr/bin/env python3
"""Feature-only preflight for premium Data Brokerage discovery endpoints.

Reads private brokerage launch gates and current public GET catalogue.
No HTTP POST, CRM database operation, service restart or public release.
"""
from __future__ import annotations
import argparse
import json
from typing import Any,Callable

from empire_os.data_brokerage_premium_enquiry import DISCOVERY,discovery_catalog
from scripts.review_data_brokerage_sales_activation_20261018 import (
    review as private_sales_review,
)
from scripts.review_data_brokerage_public_interest_20261018 import (
    inspect as public_visibility_review,
)

SCHEMA="empire.data_brokerage.premium_discovery_release_preflight.v1"

def inspect(*,
    private:Callable[...,dict[str,Any]]=private_sales_review,
    public:Callable[...,dict[str,Any]]=public_visibility_review,
)->dict[str,Any]:
    result={
        "schema_version":SCHEMA,
        "mode":"READ_ONLY",
        "status":"HOLD_PREMIUM_DISCOVERY_SOURCE_OR_EXISTING_API_UNVERIFIED",
        "payment_activated":False,"outbound_sent":False,
        "crm_records_created":0,
        "production_api_changed":False,"public_site_changed":False,
        "database_writes":False,
        "production_premium_route_mounted":False,
        "production_premium_discovery_authorized":False,
        "execution_authority":"NONE",
    }
    try:
        local=private(show_packages=True)
        public_state=public()
        internal=discovery_catalog()
        if (
            local.get("status")!="THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD"
            or local.get("mode")!="OBSERVE"
            or local.get("payment_activated") is not False
            or local.get("outbound_sent") is not False
            or local.get("database_writes") is not False
            or public_state.get("status")!="ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS"
            or public_state.get("public_entry_match_count")!=1
            or public_state.get("private_recurring_package_count")!=2
            or public_state.get("website_mutation") is not False
            or public_state.get("database_writes") is not False
            or internal.get("status")!="UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED"
            or len(internal.get("offers",()))!=2
            or any(item.get("approved_price_cents") is not None
                    or item.get("price_approved") is not False
                    for item in internal["offers"])
        ):
            result["stage"]="CANONICAL_BROKERAGE_COMMERCIAL_AUTHORITY_HOLD"
            return result
        expected={"agency_white_label_search","portfolio_geography_intelligence"}
        if {x["draft_source_offer_code"] for x in internal["offers"]}!=expected:
            result["stage"]="DISCOVERY_OFFER_MAPPING_DRIFT"
            return result
        result.update(
            status="PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD",
            stage="PUBLIC_AND_PRIVATE_CATALOGS_ALIGNED",
            premium_unpriced_proposals=2,
            existing_public_entry_enquiry_options=1,
            existing_public_offers_count=public_state.get("public_enquiry_offers_total"),
            premium_discovery_skus=sorted(DISCOVERY),
            actual_buyer_discovery_enquiries_verified=0,
            recurring_price_published=False,
            existing_canonical_crm_rpc_reused=True,
            existing_gateway_origin_rate_limit_contract_required=True,
            existing_frontend_unpriced_option_rendering_verified=False,
            end_to_end_public_enquiry_to_founder_crm_verified=False,
            astra_owned_frontend_changes_required=True,
            next_action="REVIEW_ASTRA_SITE_AND_PRIVATELY_MOUNT_ONLY_AFTER_RELEASE_SIGNOFF",
        )
    except (OSError,ValueError,TypeError,KeyError):
        result["stage"]="SOURCE_PREVIEW_UNAVAILABLE"
    return result

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_FLAG_REQUIRED"}))
        return 2
    result=inspect()
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result["status"]=="PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD" else 2

if __name__=="__main__":
    raise SystemExit(main())
