"""Read-only bridge from engineering test evidence to EmpireOS incident reporting.

No shell execution, service restarts, database writes or authority promotion.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from empire_os.engineering_incident_adapter import inspect_pytest_log
from empire_os.incident_manager import build_incident_report


def build_engineering_health_report(log_path: str | Path) -> dict[str, Any]:
    regression = inspect_pytest_log(log_path)
    report = build_incident_report({"findings": regression["incidents"]})
    return {
        "schema_version": "empire.engineering-health.v1",
        "regression_status": regression["status"],
        "failed_cases": regression.get("failed_cases", []),
        "incident_report": report,
        "healthy": regression["status"] == "PASSED" and report["incident_count"] == 0,
        "execution_authority": "none",
        "auto_repair_permitted": False,
    }
