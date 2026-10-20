"""Refresh real permitted Lead Smart source observations; never touch the call switch."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

ROOT=Path("/srv/empire_os")
PYTHON=ROOT/".venv/bin/python"
STEPS=(
 "scripts.run_lead_smart_coverage_observer",
 "scripts.materialize_lead_smart_coverage_intelligence",
 "scripts.materialize_lead_smart_zip_gate",
 "scripts.run_lead_smart_ringba_tracking_observer",
 "scripts.materialize_lead_smart_tracking_verification",
)

def refresh():
    results=[]
    for module in STEPS:
        result=subprocess.run([str(PYTHON),"-B","-m",module],
            cwd=ROOT,timeout=110,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,check=False)
        results.append({"source":module,"exit_code":result.returncode})
        # An upstream failure must not be disguised with new timestamps.
        if result.returncode!=0:
            break
    return {"source_refresh_completed":len(results)==len(STEPS) and
            all(x["exit_code"]==0 for x in results),
            "modules":results,
            "call_control_modified":False,
            "provider_route_modified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--read-only-check",action="store_true")
    a=p.parse_args()
    if a.read_only_check:
        print(json.dumps({"status":"PREVIEW","modules":list(STEPS)}))
        return 0
    state=refresh()
    print(json.dumps(state,sort_keys=True))
    return 0 if state["source_refresh_completed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
