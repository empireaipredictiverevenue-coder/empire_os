"""Deterministic read-only acquisition-to-Founder-CRM evidence reconciliation."""
from __future__ import annotations

from copy import deepcopy
import json
import subprocess

import pytest

from scripts import reconcile_founder_sales_handoff_aggregate_readonly as audit


def source(*, total=0, unlinked=0, missing_binding=0,
           inconsistent=0, commercial=None, predictive=0):
    if commercial is None:
        commercial = total - predictive
    return {
        "schema_version": "empire.founder.canonical_sales_source_aggregate.v1",
        "mode": "OBSERVE", "read_only": True, "database_writes": False,
        "status": (
            "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE"
            if total == 0
            else "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED"
        ),
        "commercial_acquisition_rows": commercial,
        "predictive_acquisition_rows": predictive,
        "sales_acquisition_rows": total,
        "distinct_sales_prospects": min(total, total),
        "source_evidence_consistent_rows": total - inconsistent,
        "entity_unlinked_acquisition_rows": unlinked,
        "founder_binding_exact_one_rows": total - missing_binding,
        "founder_binding_missing_or_ambiguous_rows": missing_binding,
        "founder_crm_delivery_verified": False,
        "execution_authority": "NONE",
    }


def tenant(*, commercial=0, predictive=0, total=None):
    if total is None:
        total = commercial + predictive
    return {
        "schema_version": "empire.founder.sales_crm_visibility_readonly.v1",
        "mode": "OBSERVE", "read_only": True,
        "prospect_ingest_performed": False,
        "tenant_binding_mutated": False,
        "status": (
            "TENANT_VISIBLE_SALES_PROSPECTS_PRESENT"
            if commercial or predictive
            else "NO_TENANT_VISIBLE_SALES_PROSPECTS"
        ),
        "visible_commercial_sales_prospects": commercial,
        "visible_predictive_revenue_prospects": predictive,
        "visible_total_prospects": total,
        "founder_crm_delivery_verified": False,
        "execution_authority": "NONE",
    }


@pytest.mark.parametrize("s,t,expected", [
    (source(), tenant(), "NO_CANONICAL_SALES_ACQUISITION_OBSERVED"),
    (source(total=2, inconsistent=1), tenant(),
     "CANONICAL_INTAKE_EVIDENCE_INCONSISTENT"),
    (source(total=2, unlinked=1, missing_binding=1), tenant(),
     "IDENTITY_LINK_GAP_DETECTED"),
    (source(total=2, missing_binding=2), tenant(),
     "TENANT_BINDING_GAP_DETECTED"),
    (source(total=1), tenant(), "CRM_PROJECTION_GAP_DETECTED"),
    (source(total=2, commercial=1, predictive=1), tenant(commercial=1),
     "NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH"),
])
def test_reconciles_only_aggregate_verified_contracts(s, t, expected):
    result = audit.reconcile(s, t)
    assert result["status"] == expected
    assert result["founder_crm_delivery_verified"] is False
    assert result["raw_customer_rows_read"] is False
    assert result["database_writes"] is False
    assert result["tenant_binding_changed"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "NONE"
    assert result["customer_identifiers_disclosed"] is False


@pytest.mark.parametrize("altered,expected", [
    ({"status": "UNVERIFIED"}, "CANONICAL_SOURCE_PROBE_UNVERIFIED"),
    ({"database_writes": True}, "CANONICAL_SOURCE_PROBE_UNVERIFIED"),
    ({"read_only": False}, "CANONICAL_SOURCE_PROBE_UNVERIFIED"),
    ({"schema_version": "unknown.v0"}, "CANONICAL_SOURCE_PROBE_UNVERIFIED"),
])
def test_source_must_match_exact_readonly_contract(altered, expected):
    bad = {**source(), **altered}
    result = audit.reconcile(bad, tenant())
    assert result["status"] == "HELD_UNVERIFIED_EVIDENCE"
    assert result["reason_code"] == expected


@pytest.mark.parametrize("altered", [
    {"status": "UNVERIFIED"},
    {"tenant_binding_mutated": True},
    {"prospect_ingest_performed": True},
    {"read_only": False},
    {"schema_version": "fake.v0"},
])
def test_tenant_reader_must_match_existing_verified_contract(altered):
    result = audit.reconcile(source(), {**tenant(), **altered})
    assert result["status"] == "HELD_UNVERIFIED_EVIDENCE"
    assert result["reason_code"] == "TENANT_SCOPED_CRM_PROBE_UNVERIFIED"


@pytest.mark.parametrize("altered", [
    {"sales_acquisition_rows": True},
    {"distinct_sales_prospects": -1},
    {"entity_unlinked_acquisition_rows": "0"},
    {"source_evidence_consistent_rows": 2},
    {"founder_binding_missing_or_ambiguous_rows": 1},
    {"commercial_acquisition_rows": 1},
])
def test_malformed_and_contradictory_counts_fail_closed(altered):
    result = audit.reconcile({**source(), **altered}, tenant())
    assert result["status"] == "HELD_UNVERIFIED_EVIDENCE"
    assert result["founder_crm_delivery_verified"] is False


def test_missing_required_count_always_holds():
    item = source()
    item.pop("source_evidence_consistent_rows")
    response = audit.reconcile(item, tenant())
    assert response["status"] == "HELD_UNVERIFIED_EVIDENCE"


def test_no_root_means_no_existing_probe_is_executed():
    attempts = []
    result = audit.run(
        privileged=False,
        operator=lambda command: attempts.append(command),
    )
    assert result["status"] == "HELD_PRIVILEGED_READONLY_OPERATOR_REQUIRED"
    assert attempts == []


def test_only_exact_existing_probes_invoked_once_with_correct_os_identity():
    seen = []
    one, two = audit.commands()

    def operator(command):
        seen.append(command)
        return source() if command == one else tenant()

    result = audit.run(privileged=True, operator=operator)
    assert seen == [one, two]
    assert one[1:3] == ("-m", audit.SOURCE_MODULE)
    assert two[:4] == ("/usr/sbin/runuser", "-u", "ubuntu", "--")
    assert two[-2:] == ("-m", audit.TENANT_MODULE)
    assert result["status"] == "NO_CANONICAL_SALES_ACQUISITION_OBSERVED"


def test_reader_failure_never_opens_unauthorized_account():
    seen = []
    first, second = audit.commands()

    def operator(command):
        seen.append(command)
        if command == second:
            raise audit.EvidenceHeld("BOUNDED_PROBE_PROBLEM")
        return source()

    result = audit.run(privileged=True, operator=operator)
    assert result["status"] == "HELD_BOUNDED_SOURCE_PROBE_FAILED"
    assert seen == [first, second]
    assert result["outbound_sent"] is False


def test_command_runner_never_logs_raw_stderr_and_rejects_raw_stdout(monkeypatch):
    monkeypatch.setattr(audit.subprocess, "run", lambda *_a, **kw: (
        type("Proc", (), {
            "returncode": 0,
            "stdout": '{"secret":"abc","customer_email":"buyer@example.invalid"}',
        })()
    ))
    first, _ = audit.commands()
    result = audit._read_process(first)
    # Parsing here is internal only; reconcile never emits any unknown fields.
    assert isinstance(result, dict)
    exposed = audit.reconcile(source(), tenant())
    assert "buyer@example.invalid" not in json.dumps(exposed)
    assert "customer_email" not in json.dumps(exposed)


def test_runner_invokes_exact_readonly_command_and_discards_driver_stderr(monkeypatch):
    found = []

    class Proc:
        returncode = 0
        stdout = json.dumps(source())

    def runner(command, **kwargs):
        found.append((command, kwargs))
        return Proc()

    monkeypatch.setattr(audit.subprocess, "run", runner)
    report = audit._read_process(audit.commands()[0])
    assert report["status"] == "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE"
    cmd, kw = found[0]
    assert cmd == audit.commands()[0]
    assert kw["stderr"] is subprocess.DEVNULL
    assert kw["timeout"] <= 24
    assert kw["check"] is False
    assert kw["cwd"] == audit.ROOT
    assert "POSTGRES_PASSWORD" not in kw["env"]


def test_unexpected_command_before_process_rejected(monkeypatch):
    monkeypatch.setattr(
        audit.subprocess,
        "run",
        lambda *_a, **_kw: pytest.fail("UNEXPECTED_COMMAND_EXECUTED"),
    )
    with pytest.raises(audit.EvidenceHeld, match="UNEXPECTED_PROBE_COMMAND"):
        audit._read_process(("bash", "-c", "printf secret"))


def test_default_cli_is_non_executing(monkeypatch, capsys):
    monkeypatch.setattr(
        audit,
        "run",
        lambda: pytest.fail("DEFAULT_MUST_NOT_RUN_PRIVILEGED_PROBES"),
    )
    assert audit.main([]) == 0
    reply = json.loads(capsys.readouterr().out)
    assert reply["status"] == "REVIEW_ONLY_NOT_RUN"
    assert reply["founder_crm_delivery_verified"] is False
