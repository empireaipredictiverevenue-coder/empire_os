#!/usr/bin/env python3
"""Read-only premium brokerage public gateway release boundary preflight.

Inspects existing checkout/gateway routing tables without creating routes.
Uses the previously reviewed public-catalog GET-only preflight. No CRM POST,
money, mail, credential access, database write, frontend edit or restart.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from empire_os.data_brokerage_premium_gateway_adapter import (
    PUBLIC_PATH,PRIVATE_PATH,safe_public_discovery_catalog,
)
from scripts.review_data_brokerage_premium_enquiry_20261018 import (
    inspect as read_private_preflight,
)

SCHEMA="empire.data_brokerage.two_hop_gateway_release_boundary.v1"

def read_existing_routes()->tuple[set[str],set[str]]:
    from empire_os.public_gateway import app as public_app
    from empire_os.self_serve_checkout_api import app as private_app
    return (
        {r.path for r in public_app.routes if isinstance(getattr(r,"path",None),str)},
        {r.path for r in private_app.routes if isinstance(getattr(r,"path",None),str)},
    )

def inspect(*,preflight:Callable[[],dict[str,Any]]=read_private_preflight,
            paths:Callable[[],tuple[set[str],set[str]]]=read_existing_routes,
           )->dict[str,Any]:
    result={
        "schema_version":SCHEMA,
        "status":"HOLD_PREMIUM_GATEWAY_EVIDENCE_OR_DEPLOYMENT_DRIFT",
        "mode":"READ_ONLY","outbound_sent":False,
        "database_writes":False,"crm_records_created":0,
        "public_site_changed":False,"payment_activated":False,
        "production_route_published":False,
        "real_buyer_enquiry_verified":False,
        "buyer_to_founder_crm_verified":False,
        "execution_authority":"NONE",
    }
    try:
        proof=preflight()
        if (type(proof) is not dict or
            proof.get("status")!="PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD"
            or proof.get("premium_unpriced_proposals")!=2
            or proof.get("production_premium_route_mounted") is not False
            or proof.get("production_api_changed") is not False
            or proof.get("database_writes") is not False
            or proof.get("payment_activated") is not False):
            result["failure_stage"]="PRIVATE_DISCOVERY_SOURCE_HOLD"
            return result
        public,private=paths()
        if type(public) is not set or type(private) is not set:
            result["failure_stage"]="PRODUCTION_ROUTE_TABLE_UNVERIFIED"
            return result
        if PUBLIC_PATH in public or PRIVATE_PATH in private:
            result["failure_stage"]="LIVE_ROUTE_ALREADY_CHANGED_NEEDS_SEPARATE_AUDIT"
            return result
        choices=safe_public_discovery_catalog()
        if (choices.get("count")!=2
            or any(x.get("public_approved_price_available") is not False
                   for x in choices["offers"])):
            result["failure_stage"]="UNAPPROVED_PRICE_PUBLICATION_RISK"
            return result
        result.update(
            status="TWO_HOP_PREMIUM_GATEWAY_ADAPTER_READY_RELEASE_HELD",
            stage="EXISTING_PRODUCTION_ROUTES_UNCHANGED",
            candidate_public_endpoint=PUBLIC_PATH,
            existing_private_endpoint_required=PRIVATE_PATH,
            unpriced_discovery_choices=2,
            existing_public_approved_199_enquiry_unchanged=True,
            public_route_currently_mounted=False,
            private_route_currently_mounted=False,
            simulated_canonical_crm_ingestion_tested=True,
            production_crm_delivery_proven=False,
            real_buyer_to_revenue_credential_verified=False,
            astra_ui_and_release_approval_still_required=True,
            next_action="OWNER_REVIEW_TWO_HOP_MOUNT_AND_ASTRA_UNPRICED_UI_BEFORE_PUBLIC_RELEASE",
        )
    except Exception:
        result["failure_stage"]="PREVIEW_OR_ROUTE_INTROSPECTION_UNAVAILABLE"
    return result

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_FLAG_REQUIRED"}))
        return 2
    report=inspect()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="TWO_HOP_PREMIUM_GATEWAY_ADAPTER_READY_RELEASE_HELD" else 2

if __name__=="__main__":
    raise SystemExit(main())
