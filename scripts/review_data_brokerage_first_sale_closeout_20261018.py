#!/usr/bin/env python3
"""One existing brokerage offer: private evidence, price, rights, first-sale gaps.

This is an on-disk read-only verifier, not a new CRM, inbox, brokerage DB,
checkout, mailer, commercial approval or customer-data export.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import os
import stat
from typing import Any

from empire_os.data_brokerage_product_catalog import PRODUCT_IDS
from scripts.preview_roofing_competitor_gap_sample import (
    REPORT, RECEIPT, RECEIPT_SCHEMA, ROOT,
)

CATALOG = Path("runtime/data_brokerage/internal_product_catalog_latest.json")
FOUNDER_REVIEW = Path("runtime/revenue_strike/contractor_founder_review_latest.json")
RECEIPT_SHA = "59b53c1e855481017484694e2ae7c3c3e4517394f39b599eeb8086269af2482a"
SCHEMA="empire.data_brokerage.first_sale_closeout.v1"

def _private_bytes(path:Path,limit:int)->bytes:
    meta=path.lstat()
    if not stat.S_ISREG(meta.st_mode) or stat.S_IMODE(meta.st_mode)!=0o600:
        raise ValueError("PRIVATE_ARTIFACT_PERMISSIONS_INVALID")
    if meta.st_size<=0 or meta.st_size>limit:
        raise ValueError("PRIVATE_ARTIFACT_SIZE_INVALID")
    with path.open("rb") as f:
        data=f.read(limit+1)
    if len(data)>limit:
        raise ValueError("PRIVATE_ARTIFACT_TOO_LARGE")
    return data

def _object(raw:bytes)->dict[str,Any]:
    data=json.loads(raw)
    if type(data) is not dict:
        raise ValueError("PRIVATE_ARTIFACT_SHAPE_INVALID")
    return data

def inspect(*,root:Path=ROOT)->dict[str,Any]:
    result={
        "schema_version":SCHEMA,
        "mode":"OBSERVE","read_only":True,
        "status":"HOLD_PRIVATE_BROKERAGE_EVIDENCE_UNVERIFIED",
        "revenue_or_payment_verified":False,
        "buyer_accepted_scope_verified":False,
        "original_customer_report_fulfilled":False,
        "database_mutation":False,"outbound_sent":False,
        "buyer_record_created":False,"customer_export":False,
        "payment_executed":False,"paid_api_calls":0,
        "private_report_bytes_disclosed":False,
        "first_sale_ready":False,
    }
    try:
        private=_private_bytes(root/REPORT,50_000)
        receipt=_object(_private_bytes(root/RECEIPT,10_000))
        catalog=_object(_private_bytes(root/CATALOG,128_000))
        review=_object(_private_bytes(root/FOUNDER_REVIEW,250_000))
        digest=sha256(private).hexdigest()
        if (
            digest!=RECEIPT_SHA
            or receipt.get("schema_version")!=RECEIPT_SCHEMA
            or receipt.get("report_sha256")!=digest
            or receipt.get("asset_class")!="FOUNDER_REVIEW_AI_ASSISTED_ORIGINAL_RESEARCH_DRAFT"
            or receipt.get("ai_assistance_disclosed") is not True
            or receipt.get("customer_delivery_authorized") is not False
            or receipt.get("raw_dataset_resale_authorized") is not False
            or receipt.get("outbound_sent") is not False
            or receipt.get("empiredb_writes") is not False
            or receipt.get("paid_api_calls")!=0
            or receipt.get("execution_authority")!="none"
            or catalog.get("schema_version")!="empire.data_brokerage.internal_product_catalog.v1"
            or catalog.get("mode")!="OBSERVE"
            or catalog.get("status")!="FOUR_ORIGINAL_DATA_PRODUCTS_IN_INTERNAL_BROKERAGE_REVIEW"
            or catalog.get("product_count")!=4
            or catalog.get("product_publication_authorized") is not False
            or catalog.get("billing_activation_enabled") is not False
            or catalog.get("customer_distributions_approved")!=0
            or catalog.get("verified_payment_count")!=0
            or catalog.get("independently_verified_buyer_count")!=0
            or review.get("outbound_authorized") is not False
            or review.get("canonical_contact_history_checked") is not False
            or review.get("individual_recipient_suppression_cleared") is not False
            or review.get("suppression_verified_clear") is not False
        ):
            result["failure_stage"]="RIGHTS_RECEIPT_OR_COMMERCIAL_GOVERNANCE"
            return result
        products=catalog.get("products")
        if (type(products) is not list or len(products)!=4
            or {p.get("product_id") for p in products if type(p) is dict}
               !=set(PRODUCT_IDS)
            or any(
                type(p) is not dict
                or p.get("raw_third_party_resale_cleared") is not False
                or p.get("customer_data_export_ready") is not False
                or p.get("buyer_verified") is not False
                or p.get("product_activation_enabled") is not False
                or p.get("offer_state")!="INTERNAL_PREVIEW_FOR_FOUNDER_AND_SALES_RESEARCH"
                for p in products)):
            result["failure_stage"]="PRODUCT_CATALOG_STATUS_UNTRUSTED"
            return result
        contractor_packets=review.get("packets")
        if type(contractor_packets) is not list:
            result["failure_stage"]="BUYER_REVIEW_UNTRUSTED"
            return result
        first=next((p for p in contractor_packets
                    if type(p) is dict and p.get("company_domain")=="spcroofs.com"),None)
        if first is None or first.get("outbound_authorized") is not False:
            result["failure_stage"]="SPC_RESEARCH_REVIEW_UNVERIFIED"
            return result
        result.update(
            status="BROKERAGE_PRIVATE_SAMPLE_VERIFIED_FIRST_SALE_HELD",
            report_sha256=digest,
            product_count=4,
            original_report_private_and_integrity_verified=True,
            derivative_analysis_scope="ONE_US_ROOFING_SERVICE_ONE_METRO",
            approved_offer_code="competitor_search_gap",
            list_price_usd=199,
            private_sample_not_customer_deliverable=True,
            offers_customer_deliverable_authorized=0,
            raw_third_party_data_resale_authorized=False,
            checkout_usable_or_funds_moved_verified=False,
            review_domains_count=len(contractor_packets),
            spc_research_only=True,
            current_local_serp_measured=False,
            buyer_contact_and_suppression_cleared=False,
            exact_buyer_scope_accepted=False,
            actual_paid_order_verified=False,
            production_revenue_verified=False,
            blockers=[
                "CURRENT_LOCAL_SERP_PAGE_EVIDENCE_NOT_CAPTURED",
                "BUYER_RECIPIENT_ROLE_AND_SUPPRESSION_UNVERIFIED",
                "ONE_BUYER_ACCEPTED_SCOPE_NOT_OBSERVED",
                "CHECKOUT_AND_EXTERNAL_SETTLEMENT_NOT_VERIFIED",
                "PAID_CUSTOMER_DELIVERY_NOT_VERIFIED",
                "FOUR_RAW_SOURCE_PRODUCT_RIGHTS_AND_RELEASE_HELD",
            ],
            recommended_next_action="USE_EXISTING_SPC_THREAD_FOR_REPLY_OR_SCOPE_REVIEW_NO_DUPLICATE_SEND",
        )
        return result
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        result["failure_stage"]="MISSING_UNSAFE_OR_DAMAGED_PRIVATE_SOURCE"
        return result

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",action="store_true")
    args=p.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    report=inspect()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="BROKERAGE_PRIVATE_SAMPLE_VERIFIED_FIRST_SALE_HELD" else 2

if __name__=="__main__":
    raise SystemExit(main())
