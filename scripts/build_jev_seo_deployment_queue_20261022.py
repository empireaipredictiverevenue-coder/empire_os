"""Export one private, evidence-proven SEO research-deployment task queue.

Run manually. No automated website changes, redirect, model call, CRM write
or mail. Durable immutable output can be consumed by existing Kanban later,
but must not be auto-promoted as a verified commercial task.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

from empire_os.search_intelligence.jev_seo_deployment_queue import (
    JevDeploymentQueueHeld, prepare_jev_seo_deployment_queue,
    safe_deployment_portfolio_summary,
)

DIRECTORY=Path("/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021")
TARGET=DIRECTORY/"jev_seo_evidence_to_deployment_queue_20261022.json"


def run(*, write_private: bool=False) -> dict[str,object]:
    packet=prepare_jev_seo_deployment_queue()
    summary=safe_deployment_portfolio_summary(packet)
    if not write_private:
        return {**summary, "receipt_created":False}
    if (DIRECTORY.is_symlink() or not DIRECTORY.is_dir()
            or DIRECTORY.stat().st_mode & 0o077):
        raise JevDeploymentQueueHeld("PRIVATE_EVIDENCE_DIRECTORY_UNSAFE")
    fd=os.open(str(DIRECTORY/".jev-seo-deployment-queue.lock"),
               os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"r+") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if TARGET.exists() or TARGET.is_symlink():
            raise JevDeploymentQueueHeld("DEPLOYMENT_QUEUE_RECEIPT_ALREADY_EXISTS")
        out_fd=os.open(str(TARGET),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(out_fd,"w",encoding="utf-8") as stream:
                json.dump(packet,stream,sort_keys=True,indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            TARGET.unlink(missing_ok=True)
            raise
    return {**summary,"receipt_created":True,"private_path":str(TARGET)}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--write-private",action="store_true")
    a=p.parse_args()
    try:
        response=run(write_private=a.write_private)
    except (JevDeploymentQueueHeld, OSError, ValueError) as exc:
        response={
            "status":"SEO_DEPLOYMENT_QUEUE_HELD",
            "reason":str(exc) if isinstance(exc,JevDeploymentQueueHeld)
                     else "SOURCE_OR_SECURE_FILE_UNAVAILABLE",
            "unattended_model_calls":0,
            "website_mutations":False,
            "execution_authority":"NONE",
        }
    print(json.dumps(response,sort_keys=True))


if __name__=="__main__":
    main()
