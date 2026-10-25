#!/usr/bin/env python3
"""Read-only infrastructure audit: original Cloud, protected runner and Jev."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from empire_os.predictive_cloud_core_jev_observer import (
    SERVICES,inspect_cloud_core_jev,
)

ROOT=Path("/srv/empire_os")
GUARD=Path("/opt/empire/predictive_cloud_guard_5caaa4106769")


def _run(argv:list[str])->str:
    try:
        done=subprocess.run(argv,capture_output=True,text=True,
                            timeout=3,check=False)
        if done.returncode!=0:
            return "unknown"
        return done.stdout.strip()[:4096]
    except (OSError,subprocess.TimeoutExpired):
        return "unknown"


def main(argv=None,*,root=ROOT,guard=GUARD)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"EXPLICIT_READ_ONLY_REQUIRED",
                          "execution_authority":"none"}))
        return 2
    states={
        unit:_run(["systemctl","is-active",unit])
        for unit in SERVICES
    }
    raw=_run(["systemctl","show","empire-predictive-cloud-materializer.service",
              "-p","ExecStart","--value"])
    # Observed runner path, not runtime permission to change the unit.
    expected=str(guard/"scripts/run_predictive_cloud_materializer.py")
    selected=expected if expected in raw else "NOT_SELECTED"
    try:
        report=inspect_cloud_core_jev(
            repo_root=Path(root),guard_root=Path(guard),
            effective_runner=selected,services=states,
            now=datetime.now(timezone.utc),
        )
    except (ValueError,TypeError,OSError):
        print(json.dumps({"status":"CORE_OBSERVER_HELD","execution_authority":"none"}))
        return 2
    print(json.dumps(report,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
