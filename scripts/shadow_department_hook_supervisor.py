#!/usr/bin/env python3
"""Shadow inspect existing department service; NEVER starts production hooks."""
from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
from empire_os.department_hook_supervisor import (
    validate_inventory, matches_current_service, supervise, HookSupervisorError,
)

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--inventory",default="/srv/empire_os/runtime/orchestration_integrity/service_hook_inventory_20261114.json")
    a=p.parse_args()
    manifest=json.loads(Path(a.inventory).read_text())
    jobs=validate_inventory(manifest)
    live=subprocess.run(
        ["systemctl","cat","empire-department-cycle.service"],
        capture_output=True,text=True,timeout=10,check=False,
    )
    if live.returncode or not matches_current_service(jobs,live.stdout):
        print(json.dumps({"status":"BLOCKED_SERVICE_DRIFT","executed":0}))
        return 3
    result=supervise(jobs,cycle_id="shadow-source-verified",
                     checkpoint=Path("/srv/empire_os/runtime/orchestration_integrity/hook_supervisor_candidate.json"))
    print(json.dumps({
        **result,"real_service_configuration_matched":True,
        "required_jobs":sum(not j["optional"] for j in jobs),
        "optional_jobs":sum(j["optional"] for j in jobs),
        "execution_authority":"none",
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
