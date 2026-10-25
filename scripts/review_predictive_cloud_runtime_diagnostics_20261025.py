#!/usr/bin/env python3
"""Read-only host diagnostics; no service, DB, Jev or model execution."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from empire_os.predictive_cloud_core_jev_observer import SOURCES, _read
from empire_os.predictive_cloud_runtime_diagnostics import inspect_runtime_diagnostics

ROOT = Path("/srv/empire_os")
UNIT = "empire-predictive-cloud-materializer.service"
PROPERTIES = ("Result", "ExecMainStatus", "ExecMainStartTimestamp",
              "ExecMainExitTimestamp", "ExecMainStartTimestampMonotonic",
              "ExecMainExitTimestampMonotonic")


def _service_show() -> str:
    try:
        response = subprocess.run(
            ["systemctl", "show", UNIT,
             *[part for key in PROPERTIES for part in ("-p", key)]],
            check=False, capture_output=True, text=True, timeout=3,
        )
        return response.stdout[:8192] if response.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _journal() -> str | None:
    """Bounded visible messages, not a claim of complete historical records."""
    try:
        response = subprocess.run(
            ["journalctl", "-u", UNIT, "--since=24 hours ago",
             "--no-pager", "--output=json",
             "--grep=Deactivated successfully|Failed with result",
             "-n", "1024"],
            check=False, capture_output=True, text=True, timeout=3,
        )
        if response.returncode != 0 or len(response.stdout) > 1_048_576:
            return None
        return response.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None


def main(argv=None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status": "EXPLICIT_READ_ONLY_REQUIRED",
                          "execution_authority": "none"}))
        return 2
    snapshots = {key: _read(root, path)[0] for key, (path, _, _) in SOURCES.items()}
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")[:16385]
    except OSError:
        meminfo = ""
    try:
        usage = shutil.disk_usage(root)
        disk = {"total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        disk = {}
    try:
        load = os.getloadavg()[0]
    except OSError:
        load = None
    report = inspect_runtime_diagnostics(
        now=datetime.now(timezone.utc), systemd_show=_service_show(),
        meminfo=meminfo, disk=disk, snapshots=snapshots,
        load_one=load, cpu_count=os.cpu_count(),
        journal_jsonl=_journal(),
    )
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
