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
    coverage_ok=True
    tracking_observed=False
    for index,module in enumerate(STEPS):
        if index>=3 and not coverage_ok:
            break
        result=subprocess.run([str(PYTHON),"-B","-m",module],
            cwd=ROOT,timeout=110,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,check=False)
        results.append({"source":module,"exit_code":result.returncode})
        if index<3 and result.returncode!=0:
            coverage_ok=False
            break
        if index==3:
            if result.returncode!=0:
                # Do NOT rematerialize yesterday's observation as fresh.
                # Existing independently verified assignments are evaluated
                # by the unchanged timestamp-aware launch gate (48h max).
                break
            tracking_observed=True
        if index==4 and result.returncode!=0:
            tracking_observed=False
    return {
        "source_refresh_completed":coverage_ok and len(results)>=3,
        "tracking_observation_refreshed":tracking_observed and len(results)==5,
        "tracking_assignment_checked_separately_by_launch_gate":True,
        "modules":results,
        "call_control_modified":False,
        "provider_route_modified":False,
    }

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
