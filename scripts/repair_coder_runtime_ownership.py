#!/usr/bin/env python3
"""Repair root-owned runtime state for active Empire Coder jobs only."""
from __future__ import annotations
import argparse, grp, json, os, pwd
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",default="/srv/empire_os")
    ap.add_argument("--user",default="ubuntu")
    ap.add_argument("--group",default="ubuntu")
    a=ap.parse_args()
    root=Path(a.repo_root).resolve()
    runtime=root/"runtime/coder"
    uid=pwd.getpwnam(a.user).pw_uid
    gid=grp.getgrnam(a.group).gr_gid
    task_ids=set()
    repaired=[]
    for bucket in ("pending","running","delegated"):
        for p in (runtime/"jobs"/bucket).glob("*.json"):
            try:
                st=p.stat()
                if st.st_uid==0 or st.st_gid==0:
                    os.chown(p,uid,gid)
                    repaired.append(str(p.relative_to(root)))
                x=json.loads(p.read_text())
            except (OSError,json.JSONDecodeError):
                continue
            tid=str(x.get("task_id") or "").strip()
            if tid:
                task_ids.add(tid)
    for tid in sorted(task_ids):
        safe="".join(c for c in tid if c.isalnum() or c in "_-")
        if not safe or safe!=tid: continue
        for directory in ("tasks","context"):
            p=runtime/directory/f"{safe}.json"
            if p.exists() and p.stat().st_uid==0:
                os.chown(p,uid,gid)
                repaired.append(str(p.relative_to(root)))
    print(json.dumps({
        "schema_version":"empire.coder.runtime-ownership-repair.v1",
        "status":"AVAILABLE",
        "active_task_count":len(task_ids),
        "repaired_count":len(repaired),
        "repaired":repaired,
        "repository_mutation":False,
        "business_data_mutation":False,
        "execution_authority":"runtime_state_repair_only",
    },indent=2,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
