#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.incident_manager import build_incident_report
from empire_os.engineering_health_bridge import build_engineering_health_report

CONTROL = Path("/srv/empire_os/runtime/ops_control/latest.json")
OUTPUT = Path("/srv/empire_os/runtime/incidents/latest.json")
ENGINEERING_LOG = Path("/srv/empire_os/runtime/engineering_health/pytest_latest.log")


def main() -> int:
    try:
        control = json.loads(CONTROL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        control = {}
    sentinel = control.get("sentinel") if isinstance(control, dict) else {}
    report = build_incident_report(
        sentinel if isinstance(sentinel, dict) else {}
    )
    if ENGINEERING_LOG.is_file():
        engineering = build_engineering_health_report(ENGINEERING_LOG)
        report["engineering_health"] = engineering
        engineering_diagnoses = engineering["incident_report"]["diagnoses"]
        report["diagnoses"].extend(engineering_diagnoses)
        report["incident_count"] = len(report["diagnoses"])
        report["requires_escalation"] = (
            report["requires_escalation"] or engineering["incident_report"]["requires_escalation"]
        )
        priorities = [item["commercial_priority"] for item in report["diagnoses"]]
        report["highest_priority"] = max(priorities, default=None)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
