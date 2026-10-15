#!/usr/bin/env python3
"""One-shot canonical sales-acquisition -> founder CRM aggregate reconciliation.

Read-only, *privileged operator* only. Executes the two EXISTING probes under
their respective OS identities. Does not access customer rows in Python;
prints count/evidence classifications only. Does not link entities, create
tenants, send mail, process payment, or manufacture sample enquiries.

This comparison can identify broken coverage, never claim a complete
real-customer lifecycle from aggregate counts alone.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

ROOT = Path("/srv/empire_os")
PYTHON = str(ROOT / ".venv/bin/python")
SOURCE_MODULE = "scripts.probe_canonical_sales_intake_aggregate_readonly"
TENANT_MODULE = "scripts.probe_founder_sales_visibility_readonly"
SCHEMA = "empire.founder.sales_acquisition_crm_reconciliation.v1"
MAX_RESULT_BYTES = 14_000

# Nothing in an output includes names, emails, contact domains or prospect IDs.
SOURCE_COUNTS = (
    "commercial_acquisition_rows", "predictive_acquisition_rows",
    "sales_acquisition_rows", "distinct_sales_prospects",
    "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
    "founder_binding_exact_one_rows",
    "founder_binding_missing_or_ambiguous_rows",
)
TENANT_COUNTS = (
    "visible_commercial_sales_prospects",
    "visible_predictive_revenue_prospects",
    "visible_total_prospects",
)


class EvidenceHeld(Exception):
    pass


def commands() -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        (PYTHON, "-m", SOURCE_MODULE),
        ("/usr/sbin/runuser", "-u", "ubuntu", "--", PYTHON, "-m", TENANT_MODULE),
    )


def _read_process(command: tuple[str, ...]) -> dict[str, Any]:
    if command not in commands():
        raise EvidenceHeld("UNEXPECTED_PROBE_COMMAND")
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            env={
                "PATH": "/usr/bin:/bin",
                "LC_ALL": "C",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PGCONNECT_TIMEOUT": "4",
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=24,
            check=False,
        )
        # Untrusted stdout can contain private details after a regression.
        # Reject any oversized or altered envelope before parsing or printing.
        if proc.returncode != 0 or len(proc.stdout) > MAX_RESULT_BYTES:
            raise EvidenceHeld("BOUND_READONLY_PROBE_UNAVAILABLE")
        parsed = json.loads(proc.stdout.strip())
        if not isinstance(parsed, dict):
            raise EvidenceHeld("UNEXPECTED_PROBE_RESPONSE_TYPE")
        return parsed
    except EvidenceHeld:
        raise
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        raise EvidenceHeld("BOUND_READONLY_PROBE_UNAVAILABLE") from None


def _counts(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, int]:
    if not isinstance(data, dict):
        raise EvidenceHeld("UNTRUSTED_PROBE_REPORT")
    values = {}
    for key in keys:
        val = data.get(key)
        if type(val) is not int or val < 0 or val > 1_000_000_000:
            raise EvidenceHeld("PROBE_AGGREGATE_SCHEMA_INVALID")
        values[key] = val
    return values


def reconcile(source: dict[str, Any], tenant: dict[str, Any]) -> dict[str, Any]:
    flags = {
        "schema_version": SCHEMA,
        "status": "HELD_UNVERIFIED_EVIDENCE",
        "read_only": True,
        "raw_customer_rows_read": False,
        "customer_identifiers_disclosed": False,
        "tenant_binding_changed": False,
        "database_writes": False,
        "outbound_sent": False,
        "payment_executed": False,
        "founder_crm_delivery_verified": False,
        "execution_authority": "NONE",
    }

    if (source.get("schema_version") !=
            "empire.founder.canonical_sales_source_aggregate.v1"
            or source.get("mode") != "OBSERVE"
            or source.get("read_only") is not True
            or source.get("database_writes") is not False
            or source.get("status") not in (
                "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE",
                "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED",
            )):
        flags["reason_code"] = "CANONICAL_SOURCE_PROBE_UNVERIFIED"
        return flags
    if (tenant.get("schema_version") !=
            "empire.founder.sales_crm_visibility_readonly.v1"
            or tenant.get("mode") != "OBSERVE"
            or tenant.get("read_only") is not True
            or tenant.get("prospect_ingest_performed") is not False
            or tenant.get("tenant_binding_mutated") is not False
            or tenant.get("status") not in (
                "NO_TENANT_VISIBLE_SALES_PROSPECTS",
                "TENANT_VISIBLE_SALES_PROSPECTS_PRESENT",
            )):
        flags["reason_code"] = "TENANT_SCOPED_CRM_PROBE_UNVERIFIED"
        return flags

    try:
        s = _counts(source, SOURCE_COUNTS)
        t = _counts(tenant, TENANT_COUNTS)
        total = s["sales_acquisition_rows"]
        if (s["commercial_acquisition_rows"] + s["predictive_acquisition_rows"]
                != total
                or s["distinct_sales_prospects"] > total
                or s["source_evidence_consistent_rows"] > total
                or s["entity_unlinked_acquisition_rows"] > total
                or s["founder_binding_exact_one_rows"] +
                   s["founder_binding_missing_or_ambiguous_rows"] != total
                or t["visible_commercial_sales_prospects"] +
                   t["visible_predictive_revenue_prospects"] >
                   t["visible_total_prospects"]):
            raise EvidenceHeld("CONTRADICTORY_ACQUISITION_COUNTS")
    except EvidenceHeld as e:
        flags["reason_code"] = str(e)
        return flags

    flags.update({
        **s,
        **t,
        "source_evidence_consistent": (
            s["source_evidence_consistent_rows"] == total
        ),
        "tenant_scope_evidence_complete": (
            s["founder_binding_exact_one_rows"] == total
        ),
    })
    if total == 0:
        flags["status"] = "NO_CANONICAL_SALES_ACQUISITION_OBSERVED"
        flags["next_action"] = "WAIT_FOR_GENUINE_OPTED_IN_ENQUIRY"
    elif s["source_evidence_consistent_rows"] != total:
        flags["status"] = "CANONICAL_INTAKE_EVIDENCE_INCONSISTENT"
        flags["next_action"] = "AUDIT_SOURCE_RECEIPT_PRIVATELY"
    elif s["entity_unlinked_acquisition_rows"] > 0:
        flags["status"] = "IDENTITY_LINK_GAP_DETECTED"
        flags["next_action"] = "VERIFY_BUSINESS_ENTITY_MATCH_BEFORE_LINKING"
    elif s["founder_binding_missing_or_ambiguous_rows"] > 0:
        flags["status"] = "TENANT_BINDING_GAP_DETECTED"
        flags["next_action"] = "REVIEW_FOUNDER_TENANT_BINDING_PROVENANCE"
    elif (t["visible_commercial_sales_prospects"] +
          t["visible_predictive_revenue_prospects"]) == 0:
        flags["status"] = "CRM_PROJECTION_GAP_DETECTED"
        flags["next_action"] = "VERIFY_TENANT_SCOPED_READER_ROLE_AND_VIEW"
    else:
        flags["status"] = "NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH"
        flags["next_action"] = "VERIFY_EXACT_GENUINE_ENQUIRY_LINEAGE"

    # Even identical totals or correct RLS cannot prove a particular
    # source receipt corresponds to a visible row or a paid customer.
    flags["founder_crm_delivery_verified"] = False
    return flags


def run(
    *,
    privileged: bool | None = None,
    operator: Callable[[tuple[str, ...]], dict[str, Any]] = _read_process,
) -> dict[str, Any]:
    if (os.geteuid() == 0 if privileged is None else privileged) is not True:
        return {
            "schema_version": SCHEMA,
            "status": "HELD_PRIVILEGED_READONLY_OPERATOR_REQUIRED",
            "read_only": True,
            "database_writes": False,
            "outbound_sent": False,
            "founder_crm_delivery_verified": False,
            "execution_authority": "NONE",
        }
    try:
        one, two = commands()
        source = operator(one)
        tenant = operator(two)
        return reconcile(source, tenant)
    except EvidenceHeld:
        return {
            "schema_version": SCHEMA,
            "status": "HELD_BOUNDED_SOURCE_PROBE_FAILED",
            "read_only": True,
            "database_writes": False,
            "outbound_sent": False,
            "founder_crm_delivery_verified": False,
            "execution_authority": "NONE",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate-only canonical sales to Founder CRM review"
    )
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.review_only:
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": "REVIEW_ONLY_NOT_RUN",
            "read_only": True,
            "database_writes": False,
            "founder_crm_delivery_verified": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 0
    result = run()
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"].startswith("HELD") else 0


if __name__ == "__main__":
    raise SystemExit(main())
