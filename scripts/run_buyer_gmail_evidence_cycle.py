#!/usr/bin/env python3
"""Single bounded, fail-closed Gmail buyer evidence cycle. No outbound."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/srv/empire_os")
LOCK = ROOT / "runtime/buyer_network_intelligence/gmail_cycle.lock"
STEPS = (
    "poll_buyer_gmail_readonly.py",
    "import_connected_gmail_buyer_metadata.py",
    "reconcile_buyer_email_relationships.py",
)
# Auxiliary snapshot is advisory: a Workspace outage must not block the
# existing personal-Gmail reconciliation or imply any outreach authority.
OPTIONAL_STEPS = (
    "refresh_workspace_sent_domain_receipts.py",
    "poll_workspace_solar_outreach_readonly.py",
    "run_permit_compliance_cycle_observer.py",
)

def run(*, root=ROOT, invoke=None):
    invoke = invoke or subprocess.run
    lock = root / "runtime/buyer_network_intelligence/gmail_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    env = os.environ.copy()
    env.update(EMPIRE_MODE="OBSERVE", OUTBOUND_ENABLED="0",
               EMPIRE_OUTBOUND_ENABLED="0", LIVE_OUTBOUND="0",
               PYTHONPATH=str(root))
    with os.fdopen(fd, "r+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"BLOCKED","reason_code":"CYCLE_ALREADY_RUNNING",
                    "outbound_authorized":False}
        results = []
        for step in STEPS:
            try:
                p = invoke([sys.executable, str(root / "scripts" / step), "--write"],
                           cwd=root, env=env, capture_output=True, text=True,
                           timeout=90, check=False)
                ok = p.returncode == 0
                results.append({"step":step,"status":"PASS" if ok else "FAILED",
                                "exit_code":p.returncode})
            except subprocess.TimeoutExpired:
                ok = False
                results.append({"step":step,"status":"TIMEOUT","exit_code":124})
            if not ok:
                break
        optional_results=[]
        if len(results)==len(STEPS) and all(x["status"]=="PASS" for x in results):
            for step in OPTIONAL_STEPS:
                try:
                    optional_env=(env if step!="run_permit_compliance_cycle_observer.py"
                                  else {**env,"EMPIRE_PERMIT_COMPLIANCE_OBSERVER_READONLY":"1"})
                    p=invoke([sys.executable,str(root / "scripts" / step),"--write"],
                             cwd=root,env=optional_env,capture_output=True,text=True,
                             timeout=90,check=False)
                    optional_results.append({"step":step,
                        "status":"PASS" if p.returncode==0 else "HELD",
                        "exit_code":p.returncode})
                except subprocess.TimeoutExpired:
                    optional_results.append({"step":step,"status":"TIMEOUT",
                                             "exit_code":124})
        return {"auxiliary_steps":optional_results,
                "status":"PASS" if len(results)==len(STEPS) and all(
                x["status"]=="PASS" for x in results) else "BLOCKED",
                "steps":results,"outbound_authorized":False,
                "execution_authority":"NONE"}

def main():
    argparse.ArgumentParser().parse_args()
    result=run()
    print(json.dumps(result))
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
