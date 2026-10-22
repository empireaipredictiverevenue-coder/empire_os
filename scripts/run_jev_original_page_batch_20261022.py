"""Bounded 5-owned-page Jev Decision call, never an autonomous cron or publisher."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

from empire_os.search_intelligence.jev_page_case_review import (
    JevPageBatchHeld, batch_plan, run_batch,
)
from scripts.run_search_jev_one_shot_20261021 import _read_key

DIR=Path("/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021")


def run(index: int, *, live: bool) -> dict:
    plan=batch_plan(index)
    if not live:
        return {
            "status":"BOUNDED_JEV_PAGE_BATCH_PLAN_ONLY",
            "batch_index":index, "cases":5,
            "outbound_paid_calls":0,
            "model":"typesafe/jev-1.13",
            "execution_authority":"NONE",
        }
    if DIR.is_symlink() or not DIR.is_dir() or DIR.stat().st_mode & 0o077:
        raise JevPageBatchHeld("PRIVATE_RECEIPT_DIR_UNSAFE")
    marker=DIR/f"jev_page_batch_{index}_attempted.json"
    receipt=DIR/f"jev_page_batch_{index}_20261022.json"
    lock_fd=os.open(str(DIR/".jev-page-batch.lock"),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lock_fd,"w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if receipt.exists() or marker.exists() or receipt.is_symlink() or marker.is_symlink():
            raise JevPageBatchHeld("BATCH_ALREADY_ATTEMPTED_NO_REPEAT_BILLING")
        # Acquire key first; mark attempted *before* the only network call.
        key=_read_key()
        fd=os.open(str(marker),os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:
            f.write(json.dumps({
                "schema_version":"empire.search.jev_original_page_request_attempt.v1",
                "batch_index":index,"max_calls":1,"max_cost_usd":0.001,
                "retry_authorised":False,"execution_authority":"NONE",
            })+"\n")
        reviewed=run_batch(plan,api_key=key)
        file_fd=os.open(str(receipt),os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600)
        with os.fdopen(file_fd,"w") as f:
            json.dump(reviewed,f,sort_keys=True,indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    return {
        "status":"JEV_ORIGINAL_PAGE_MODEL_BATCH_OBSERVED",
        "batch_index":index, "model_calls":1,
        "cases":reviewed["cases_reviewed"],
        "cost_usd_reported":reviewed["cost_usd_reported"],
        "model_labels_not_ground_truth":True,
        "publishing_authorised":False,
        "execution_authority":"NONE",
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--batch-index",type=int,required=True)
    p.add_argument("--live-approved-one-batch",action="store_true")
    a=p.parse_args()
    try:
        result=run(a.batch_index,live=a.live_approved_one_batch)
    except (JevPageBatchHeld,OSError,ValueError) as exc:
        result={
            "status":"JEV_PAGE_BATCH_HELD",
            "reason":str(exc) if isinstance(exc,JevPageBatchHeld)
                     else "CREDENTIAL_OR_RECEIPT_UNAVAILABLE",
            "automatic_retries":0,
            "execution_authority":"NONE",
        }
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
