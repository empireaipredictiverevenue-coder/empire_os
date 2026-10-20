"""Real existing Ops Control cycle, augmented with canonical buyer source health."""
from __future__ import annotations

import json

from test_commercial_buyer_source_health import fixtures
from test_commercial_full_ops_cycle_sandbox import _load_ops, _configure_sandbox


def _buyer_sources(root):
    buyer, scout = fixtures()
    p = root / "runtime/buyer_capacity_readiness/latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(buyer))
    q = root / "runtime/buyer_acquisition/evidence_quality_latest.json"
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_text(json.dumps(scout))
    return p, q


def _summary(ops):
    snapshot = json.loads((ops / "latest.json").read_text())
    return snapshot["adaptive_commercial_summary"]


def test_original_ops_persists_buyer_status_and_avoids_repeat_attention(
    tmp_path, monkeypatch, capsys,
):
    ops_mod = _load_ops()
    ops = _configure_sandbox(monkeypatch, ops_mod, tmp_path)
    p, q = _buyer_sources(tmp_path)

    assert ops_mod.main() == 0
    capsys.readouterr()
    first = _summary(ops)
    health = first["original_buyer_evidence_health"]
    assert health["status"] == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
    assert health["buyer_capacity_records_seen_not_verified_purchasers"] == 1023
    assert health["first_party_purchase_claim_receipts_not_contracts"] == 2
    assert first["original_buyer_evidence_transition"]["status"] == "INITIAL_BUYER_EVIDENCE_BASELINE"

    assert ops_mod.main() == 0
    capsys.readouterr()
    second = _summary(ops)
    assert second["original_buyer_evidence_transition"]["status"] == "UNCHANGED_ORIGINAL_BUYER_EVIDENCE_HOLD"
    assert second["original_buyer_evidence_transition"]["repeated_owner_attention_suppressed"] is True

    buyer = json.loads(p.read_text())
    buyer["capacity_verified"] = 1
    p.write_text(json.dumps(buyer))
    assert ops_mod.main() == 0
    capsys.readouterr()
    third = _summary(ops)
    change = third["original_buyer_evidence_transition"]
    assert change["status"] == "OWNER_COHORT_COUNTERS_CHANGED_REQUIRE_VERIFICATION"
    assert change["owner_claim_counter_deltas_not_transactions"]["owner_capacity_verified_claim_count"] == 1
    assert change["verified_new_buyer_purchases"] is None
    assert third["original_buyer_evidence_health"]["realized_revenue_cents_claimed_by_this_report"] is None
    assert json.loads(q.read_text())["company_name"] == "PRIVATE Customer Ltd"


def test_original_ops_source_failure_does_not_hide_adaptive_control(
    tmp_path, monkeypatch, capsys,
):
    ops_mod = _load_ops()
    ops = _configure_sandbox(monkeypatch, ops_mod, tmp_path)
    p, _ = _buyer_sources(tmp_path)
    p.unlink()
    assert ops_mod.main() == 0
    capsys.readouterr()
    summary = _summary(ops)
    assert summary["available"] is True
    assert summary["original_buyer_evidence_health"]["status"] == "ORIGINAL_BUYER_SOURCE_UNAVAILABLE"
    assert summary["original_buyer_evidence_transition"]["status"] == "SOURCE_UNAVAILABLE_OR_OUTDATED_HOLD"
    assert summary["outbound_authorized"] is False


def test_original_ops_reports_order_reader_deployment_only_not_sales(
    tmp_path, monkeypatch, capsys,
):
    from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
    ops_mod = _load_ops()
    ops = _configure_sandbox(monkeypatch, ops_mod, tmp_path)
    _buyer_sources(tmp_path)
    assert ops_mod.main() == 0
    capsys.readouterr()
    first = _summary(ops)
    cap = first["original_order_outcome_reader_capability"]
    assert cap["status"] == "ORIGINAL_ORDER_OWNER_READER_NOT_DEPLOYED"
    assert cap["verified_revenue_cents"] is None
    assert cap["canonical_database_proof_observed"] is False
    monkeypatch.setattr(
        ExecutionBusDataRepository, "verified_outcome_feedback",
        lambda *_a, **_k: None, raising=False,
    )
    assert ops_mod.main() == 0
    capsys.readouterr()
    after = _summary(ops)
    capability = after["original_order_outcome_reader_capability"]
    assert capability["status"] == "ORIGINAL_ORDER_READER_METHOD_PRESENT_RELEASE_NOT_ATTESTED"
    assert capability["owner_reader_release_approved_by_this_check"] is False
    assert capability["authenticated_tenant_and_order_selected"] is False
    assert capability["verified_order_count"] is None
    assert capability["execution_authority"] == "none"
    assert after["outbound_authorized"] is False
