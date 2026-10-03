#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from empire_os.coder.jobs import LocalJobQueue
from empire_os.coder.verify_fastpath import drain_verify_jobs

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",default="/srv/empire_os")
    ap.add_argument("--runtime-root",default="/srv/empire_os/runtime/coder")
    ap.add_argument("--max-jobs",type=int,default=2)
    ap.add_argument("--timeout-seconds",type=int,default=900)
    a=ap.parse_args()
    root=Path(a.repo_root).resolve()
    queue=LocalJobQueue(root,runtime_root=Path(a.runtime_root).resolve())
    x=drain_verify_jobs(queue,max_jobs=a.max_jobs,timeout_seconds=a.timeout_seconds)
    print(json.dumps({k:x[k] for k in (
        "schema_version","status","completed_count","failed_count",
        "skipped_count","model_inference","production_mutation","execution_authority"
    )},indent=2,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
