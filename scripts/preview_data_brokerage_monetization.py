#!/usr/bin/env python3
"""Read-only Empire AI brokerage revenue-option preview, not publication.

cd /srv/empire_os
./.venv/bin/python -B -m scripts.preview_data_brokerage_monetization --read-only
./.venv/bin/python -B -m scripts.preview_data_brokerage_monetization --read-only --show-options
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import stat

from empire_os.data_brokerage_monetization_portfolio import (
    build_monetization_portfolio,validate_portfolio,
)

ROOT=Path("/srv/empire_os")
PRIVATE_CATALOG=Path("runtime/data_brokerage/internal_product_catalog_latest.json")
MAX_BYTES=128_000

def source_catalog(root:Path=ROOT)->dict:
    path=root/PRIVATE_CATALOG
    st=path.lstat()
    if (not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o600
        or st.st_size<100 or st.st_size>MAX_BYTES):
        raise ValueError("PRIVATE_CATALOG_CUSTODY_INVALID")
    with path.open("rb") as f:
        raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("PRIVATE_CATALOG_TOO_LARGE")
    obj=json.loads(raw)
    if type(obj) is not dict:
        raise ValueError("PRIVATE_CATALOG_NOT_OBJECT")
    return obj

def preview(*,root:Path=ROOT,show_options:bool=False)->dict:
    safe={
        "status":"HOLD_BROKERAGE_CATALOG_OR_RIGHTS_UNVERIFIED",
        "mode":"OBSERVE","read_only":True,
        "outbound_sent":False,"customer_delivery_enabled":False,
        "payment_processed":False,"database_writes":False,
        "raw_data_exported":False,
    }
    try:
        private=source_catalog(root)
        report=build_monetization_portfolio(private)
        if not validate_portfolio(report):
            raise ValueError("PORTFOLIO_CLAIM_INCONSISTENT")
        if show_options:
            # Safe structured internal commercial plans; only derived
            # price hypotheses, IDs, priority and rights state.
            return report
        return {
            "status":report["status"],"mode":"OBSERVE","read_only":True,
            "existing_product_count":report["existing_product_count"],
            "monetization_options":report["option_count"],
            "distribution_channels":report["route_count"],
            "first_revenue_route":"ONE_SCOPED_ORIGINAL_REPORT_DIRECT_B2B",
            "repeat_revenue_route":"WHITE_LABEL_OR_SUBSCRIPTION_AFTER_EVIDENCE",
            "enterprise_route":"PRIVATE_DATA_API_OR_LICENSE_AFTER_BUYER_AND_RIGHTS",
            "price_values_are_unvalidated_hypotheses":True,
            "paid_marketplace_setup_performed":False,
            "external_provider_registration":False,
            "outbound_sent":False,"customer_delivery_enabled":False,
            "payment_processed":False,"realised_revenue_verified":False,
            "database_writes":False,"raw_data_exported":False,
            "execution_authority":"NONE",
        }
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        return safe

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    parser.add_argument("--show-options",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    result=preview(show_options=args.show_options)
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result["status"]=="DATA_BROKERAGE_MULTICHANNEL_PRICING_HYPOTHESES_PREPARED" else 2

if __name__=="__main__":
    raise SystemExit(main())
