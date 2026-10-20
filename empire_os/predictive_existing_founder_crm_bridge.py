"""On-demand, read-only consumer of the EXISTING founder CRM sales reader.

This is a visibility check, not an enquiry, customer identity, order or sale.
No new DB role, migration, service, CRM write or source-owner collector.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import pwd
from pathlib import Path
import stat
import subprocess
from typing import Any, Callable, Mapping

SCHEMA = "empire.predictive_revenue.existing_founder_sales_crm_bridge.v1"
PROBE_SCHEMA = "empire.founder.sales_crm_visibility_readonly.v1"
ROOT = Path("/srv/empire_os")
MODULE = "scripts.probe_founder_sales_visibility_readonly"
SOURCE_FILE = ROOT / "scripts/probe_founder_sales_visibility_readonly.py"
PYTHON = ROOT / ".venv/bin/python"
COUNTS = (
    "visible_commercial_sales_prospects",
    "visible_predictive_revenue_prospects",
    "visible_total_prospects",
)
MAX_STDOUT = 12_000


def held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "EXISTING_FOUNDER_CRM_READER_HELD",
        "reason_code": reason,
        "counts": None,
        "canonical_original_acquisition_probe_checked": False,
        "original_customer_order_authenticated": False,
        "crm_customer_specific_source_receipt_authenticated": False,
        "first_customer_purchasing_authority_verified": False,
        "realized_revenue_proven": False,
        "crm_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def review_existing_crm_reader(
    report: Mapping[str, Any], *, read_at: datetime,
) -> dict[str, Any]:
    """Validate typed source-owner snapshot, reveal only the three counts."""
    if not isinstance(read_at, datetime) or read_at.utcoffset() is None:
        raise ValueError("trusted review timestamp required")
    if not isinstance(report, Mapping):
        return held("UNTRUSTED_OWNER_REPORT")
    if (report.get("schema_version") != PROBE_SCHEMA
            or report.get("mode") != "OBSERVE"
            or report.get("read_only") is not True
            or report.get("execution_authority") != "NONE"
            or report.get("raw_customer_rows_read") is not False
            or report.get("tenant_binding_mutated") is not False
            or report.get("prospect_ingest_performed") is not False
            or report.get("outbound_authorized") is not False
            or report.get("payment_authorized") is not False
            or report.get("canonical_global_intake_count_proven") is not False
            or report.get("website_to_founder_visibility_proven") is not False):
        return held("OWNER_REPORT_NOT_EXACT_READ_ONLY_CONTRACT")
    if report.get("status") not in (
        "NO_TENANT_VISIBLE_SALES_PROSPECTS",
        "TENANT_VISIBLE_SALES_PROSPECTS_PRESENT",
    ) or report.get("reason_code") != "CANONICAL_SOURCE_RECEIPTS_NOT_CHECKED":
        return held("CRM_OWNER_STATUS_UNVERIFIED")
    counts: dict[str, int] = {}
    for key in COUNTS:
        value = report.get(key)
        if type(value) is not int or not 0 <= value <= 1_000_000_000:
            return held("CRM_OWNER_COUNT_INVALID")
        counts[key] = value
    c, p, n = (counts[key] for key in COUNTS)
    if c + p > n or (c + p > 0) != (
        report["status"] == "TENANT_VISIBLE_SALES_PROSPECTS_PRESENT"
    ):
        return held("CRM_OWNER_COUNT_STATUS_CONTRADICTION")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": (
            "TENANT_VISIBLE_SALES_COHORT_PRESENT_SOURCE_UNVERIFIED"
            if c + p > 0 else
            "NO_TENANT_VISIBLE_SALES_PROSPECTS_SOURCE_UNVERIFIED"
        ),
        "observed_at_utc": read_at.astimezone(timezone.utc).isoformat(),
        "counts": counts,
        "canonical_original_acquisition_probe_checked": False,
        "original_customer_order_authenticated": False,
        "crm_customer_specific_source_receipt_authenticated": False,
        "first_customer_purchasing_authority_verified": False,
        "realized_revenue_proven": False,
        "next_existing_owner_action": (
            "RECONCILE_ORIGINAL_CANONICAL_SALES_SOURCE_AND_EXACT_TENANT_LINEAGE"
        ),
        "crm_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def _execute_owner_probe() -> tuple[int, str]:
    """Run the existing least-privilege producer, without shell or privilege elevation."""
    if os.geteuid() != pwd.getpwnam("ubuntu").pw_uid:
        raise ValueError("existing Ubuntu reader identity required")
    if SOURCE_FILE.is_symlink() or not SOURCE_FILE.is_file():
        raise ValueError("existing owner module absent")
    info = SOURCE_FILE.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size > 35_000
            or info.st_mode & 0o022):
        raise ValueError("unsafe existing owner module permissions")
    result = subprocess.run(
        (str(PYTHON), "-B", "-m", MODULE),
        cwd=str(ROOT),
        env={
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PGCONNECT_TIMEOUT": "4",
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=22,
        check=False,
    )
    if len(result.stdout.encode("utf-8")) > MAX_STDOUT:
        raise ValueError("oversized owner source output")
    return result.returncode, result.stdout


def run_existing_founder_crm_review(
    *, reader: Callable[[], tuple[int, str]] = _execute_owner_probe,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Never print untrusted subprocess output or escalate privileged source roles."""
    try:
        code, stdout = reader()
        if (type(code) is not int or code != 0
                or not isinstance(stdout, str)
                or len(stdout.encode("utf-8")) > MAX_STDOUT):
            return held("EXISTING_CRM_PROBE_UNAVAILABLE")
        report = json.loads(stdout)
        return review_existing_crm_reader(
            report, read_at=as_of or datetime.now(timezone.utc),
        )
    except (OSError, ValueError, TypeError, UnicodeError,
            json.JSONDecodeError, subprocess.TimeoutExpired):
        return held("EXISTING_CRM_PROBE_UNAVAILABLE")
