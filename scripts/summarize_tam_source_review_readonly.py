#!/usr/bin/env python3
"""Inspect existing root-private TAM source review; print aggregate-only diagnostics.

No DB access, no public HTTP, no record dumps or passwords. Existing review
files are not modified. This is intentionally narrower than arbitrary JSON IO.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import stat
import sys

from empire_os.tam_source_acquisition_connector import _clean_name

PRIVATE_DIR=Path("/var/lib/empire/source-acquisition-review")
APPROVED_SCHEMAS={
    "empire.tam-first-party-discovery-review.v1",
}
MAX_FILE_BYTES=8*1024*1024

def report_summary(path: Path, *, folder: Path=PRIVATE_DIR) -> dict:
    if os.geteuid()!=0:
        raise ValueError("AUTHORISED_ROOT_REQUIRED")
    if (path.parent!=folder or
        not re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{12}[.]json",path.name)):
        raise ValueError("PRIVATE_REPORT_PATH_OUTSIDE_APPROVED_DIRECTORY")
    rootstat=os.lstat(folder)
    if (not stat.S_ISDIR(rootstat.st_mode) or
        rootstat.st_uid!=0 or rootstat.st_mode&0o077):
        raise ValueError("PRIVATE_REPORT_DIRECTORY_UNSAFE")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        fs=os.fstat(fd)
        if (not stat.S_ISREG(fs.st_mode) or fs.st_uid!=0
            or fs.st_mode&0o077 or not 0<fs.st_size<=MAX_FILE_BYTES):
            raise ValueError("PRIVATE_REPORT_FILE_UNSAFE")
        with os.fdopen(fd,"r",encoding="utf-8") as stream:
            fd=-1
            data=json.load(stream)
    finally:
        if fd>=0:os.close(fd)
    return summarize_review_payload(data)


def summarize_review_payload(data: dict) -> dict:
    """Pure, aggregate-only interpretation of already-authorized private JSON."""
    if (not isinstance(data,dict) or
        data.get("schema_version") not in APPROVED_SCHEMAS
        or data.get("mode")!="OBSERVE"
        or data.get("source")!="first_party_search"
        or data.get("database_write") is not False
        or data.get("acquisitions_appended")!=0
        or data.get("outbound_sent") is not False
        or not isinstance(data.get("findings"),list)
        or len(data["findings"])>5):
        raise ValueError("PRIVATE_REVIEW_SCHEMA_NOT_APPROVED")
    reasons=Counter()
    statuses=Counter()
    for row in data["findings"]:
        if not isinstance(row,dict):
            raise ValueError("INVALID_PRIVATE_REVIEW_FINDING")
        state=str(row.get("review_state") or "")
        if state not in {
            "AMBIGUOUS_OR_MISSING_DISCOVERED_HOST",
            "DISCOVERED_SITE_IDENTITY_UNVERIFIED",
            "DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW",
        }:
            raise ValueError("UNKNOWN_PRIVATE_REVIEW_STATE")
        statuses[state]+=1
        if state=="AMBIGUOUS_OR_MISSING_DISCOVERED_HOST":
            reasons["NO_UNIQUE_INDEPENDENT_CANDIDATE_HOST"]+=1
            continue
        if not row.get("source_url"):
            reasons["PUBLIC_SITE_OR_SAME_HOST_UNVERIFIED"]+=1
            continue
        names=row.get("observed_business_names")
        if not isinstance(names,list) or not names:
            reasons["SITE_RETRIEVED_BUT_NO_BUSINESS_NAME_EVIDENCE"]+=1
            continue
        expected=_clean_name(row.get("canonical_name"))
        if not expected or not any(
            isinstance(n,str) and _clean_name(n)==expected for n in names
        ):
            reasons["SITE_BUSINESS_NAME_DOES_NOT_EXACTLY_MATCH"]+=1
            continue
        if state=="DISCOVERED_SITE_IDENTITY_UNVERIFIED":
            reasons["SEARCH_FABRIC_IDENTITY_GUARD_REJECTED"]+=1
        else:
            reasons["REVIEW_CANDIDATE_NOT_LEDGER_APPROVED"]+=1
    return {
        "schema_version":"empire.tam-first-party-review-diagnostic.v1",
        "status":"READ_ONLY_AGGREGATE_PRIVATE_REVIEW_DIAGNOSTIC",
        "source_report_schema":data["schema_version"],
        "mode":"OBSERVE",
        "selected_entities":data.get("entities_selected_for_search"),
        "candidates":data.get("search_candidates_before_cross_entity_filter"),
        "public_site_probes_attempted":data.get("website_probes_attempted"),
        "findings_count":len(data["findings"]),
        "review_states":dict(sorted(statuses.items())),
        "rejection_reason_counts":dict(sorted(reasons.items())),
        "source_private_report_unchanged":True,
        "company_details_returned":0,
        "contacts_returned":0,
        "database_access":False,
        "network_requests":0,
        "acquisitions_appended":0,
        "outbound_sent":False,
        "execution_authority":"none",
    }

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",required=True)
    args=parser.parse_args()
    # Never include raw path, file contents or exception detail on failure.
    try:
        result=report_summary(Path(args.report))
    except Exception as exc:
        print("TAM_PRIVATE_REVIEW_DIAGNOSTIC=BLOCKED "+
              type(exc).__name__,file=sys.stderr)
        return 3
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
