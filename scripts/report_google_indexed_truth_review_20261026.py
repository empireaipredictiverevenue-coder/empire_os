#!/usr/bin/env python3
"""One-shot existing-GSC + owned-SEO-reader comparison, no Google submission.

Reuses same-loopback cached URL Inspection response and installed technical
SEO crawl; no new DB, daemon, scheduler, provider account, or publisher.
"""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path

import requests
from empire_os.search_intelligence.gsc_indexed_truth_review import review_owned_google_index_evidence
from empire_os.search_intelligence.seo_indexing_health import audit_live_indexing

DEFAULT_ROOT = Path("/home/ubuntu/empire_releases/seo_unified_existing_stack_20261026_v1")
DEFAULT_FILENAME = "google_indexed_truth_review_20261026.json"
LOCAL = "http://127.0.0.1:8771/v1/search/search-console/indexed-version/fixed"

def report(*, root:Path=DEFAULT_ROOT, write_private:bool=False)->dict:
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid!=os.geteuid():
        raise ValueError("EXISTING_RELEASE_OWNER_REQUIRED")
    if (root.stat().st_mode & 0o077):
        raise ValueError("PRIVATE_RELEASE_DIRECTORY_REQUIRED")
    res=requests.get(LOCAL,timeout=90)
    res.raise_for_status()
    raw=res.json()
    health=audit_live_indexing()
    packet=review_owned_google_index_evidence(raw,health)
    if write_private:
        target=root/DEFAULT_FILENAME
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as out:
                json.dump(packet,out,sort_keys=True,indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {"status":"ORIGINAL_GSC_INDEXED_TRUTH_PRIVATE_REVIEW_WRITTEN",
                "receipt":str(target),"indexed":packet["indexed_version_exact_verified"],
                "unknown":packet["google_url_unknown_count"],
                "critical_owned_site_issues":packet["site_audit_critical_issue_count"],
                "new_indexing_submission":False,"new_service_or_timer":False,
                "database_writes":False}
    return packet

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--write-private",action="store_true")
    args=p.parse_args()
    try:print(json.dumps(report(write_private=args.write_private),sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status":"GSC_INDEXED_TRUTH_REVIEW_HELD",
                          "reason_code":type(exc).__name__,
                          "execution_authority":"none"},sort_keys=True))
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
