#!/usr/bin/env python3
"""One official government source request, no search engine scraping or contacts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
import requests

from empire_os.a2a_official_mechanical_permit_research_v1 import (
    SCHEMA, collect_little_rock_permit_business_research,
)
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"runtime/a2a_commercial_signal_mining/official_little_rock_permit_research_v1.json"
APPROVAL="FOUNDER_APPROVED_OFFICIAL_PUBLIC_PERMIT_RESEARCH_READONLY_20261020"

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only-public-api",action="store_true",required=True)
    p.add_argument("--approval",required=True)
    p.add_argument("--lookback-days",type=int,default=45)
    args=p.parse_args()
    if args.approval!=APPROVAL:
        raise ValueError("EXPLICIT_OFFICIAL_SOURCE_OPERATOR_APPROVAL_REQUIRED")
    with requests.Session() as session:
        evidence=collect_little_rock_permit_business_research(
            session=session,lookback_days=args.lookback_days)
    if evidence.get("schema_version")!=SCHEMA or evidence.get("verified_local_hvac_lead_buyers")!=0:
        raise ValueError("UNTRUSTED_PERMIT_EVIDENCE")
    OUTPUT.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    if OUTPUT.parent.is_symlink() or OUTPUT.is_symlink():
        raise ValueError("UNSAFE_PERMIT_OUTPUT")
    fd,tmp=tempfile.mkstemp(dir=OUTPUT.parent,prefix=".official_permit_")
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(evidence,f,indent=2,sort_keys=True)
            f.write("\n")
        os.replace(tmp,OUTPUT)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print(json.dumps({
        "schema_version":SCHEMA,
        "rows":evidence["source_records_scanned"],
        "business_names_for_review":evidence["conservative_business_names_retained"],
        "newest_issue_date":evidence["recent_permit_issue_date_max"],
        "source_fresh_within_14_days":evidence["source_fresh_within_14_days"],
        "provider_response_may_be_truncated":evidence["provider_response_may_be_truncated"],
        "source_commercial_distribution_cleared":False,
        "verified_hvac_buyers":0,
        "buyer_records_modified":False,
        "messages_sent":0,
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
