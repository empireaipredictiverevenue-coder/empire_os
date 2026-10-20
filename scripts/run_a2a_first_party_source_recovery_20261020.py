#!/usr/bin/env python3
"""Operator-triggered bounded first-party company-site evidence fetch.

This is a separate explicit opt-in network read, never a background scraper.
The existing hourly research worker remains AF_UNIX only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

import requests

from empire_os.a2a_first_party_site_recovery_v1 import (
    collect_approved_first_party_sites,
)
from empire_os.a2a_first_party_site_recovery_v1 import SCHEMA

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/a2a_candidates/approved_first_party_business_sites_v1.json"
RESULT = ROOT / "runtime/a2a_commercial_signal_mining/first_party_source_recovery_v1.json"
APPROVAL = "FOUNDER_APPROVED_PUBLIC_BUSINESS_SOURCE_READ_20261020"

def _read_config() -> dict:
    if MANIFEST.is_symlink() or not MANIFEST.is_file() or MANIFEST.stat().st_size > 30_000:
        raise ValueError("UNSAFE_FIRST_PARTY_SITE_MANIFEST")
    doc = json.loads(MANIFEST.read_text())
    if not isinstance(doc, dict):
        raise ValueError("BAD_MANIFEST_ROOT")
    return doc

def _write_local(result: dict) -> None:
    RESULT.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if RESULT.parent.is_symlink() or RESULT.is_symlink():
        raise ValueError("UNSAFE_SOURCE_RECOVERY_DESTINATION")
    fd, temp = tempfile.mkstemp(prefix=".first_party_source_recovery_",dir=RESULT.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd,"w",encoding="utf8") as writer:
            json.dump(result,writer,indent=2,sort_keys=True)
            writer.write("\n")
        os.replace(temp,RESULT)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch approved public B2B company sites, read-only")
    parser.add_argument("--live-readonly",action="store_true",required=True)
    parser.add_argument("--approval",required=True)
    parser.add_argument("--max-sites",type=int,default=9)
    args = parser.parse_args()
    if args.approval != APPROVAL:
        raise ValueError("FOUNDER_APPROVAL_TOKEN_REQUIRED")
    doc = _read_config()
    with requests.Session() as session:
        result = collect_approved_first_party_sites(
            doc, session=session, max_sites=args.max_sites,
        )
    if result.get("schema_version") != SCHEMA:
        raise ValueError("SOURCE_RECOVERY_SCHEMA_MISMATCH")
    _write_local(result)
    print(json.dumps({
        "schema_version":result["schema_version"],
        "source_sites_attempted":result["websites_attempted"],
        "first_party_http_200":result["websites_http_200"],
        "sector_and_region_self_description_matches":result["self_described_sector_and_region_matches"],
        "status_by_site":[{"url":x["company_site"],"status":x["site_fetch_status"],
                           "robots":x["robots_policy"],"city_claimed":x["self_described_city_or_region_matched"]}
                          for x in result["records"]],
        "source_receipt_created":True,
        "buyers_verified":0, "new_sales_leads":0,"outbound_sent":False,
        "execution_authority":"NONE",
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
