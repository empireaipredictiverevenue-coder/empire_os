"""Adaptive commercial memory integration with the EXISTING Ops Control owner.

Synthetic fixture files only; no daemon, SMTP, CRM, DB or live writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_adaptive_ops_bridge import (
    observe_ops_adaptive_commercial, source_receipts,
)
from empire_os.conversation_control_operational_truth import (
    inspect_conversation_evidence,
)
from test_commercial_adaptive_intelligence_cli import _test_sources

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def cycle(root, previous=None, proof=None):
    return observe_ops_adaptive_commercial(
        root=root,
        previous_ops_snapshot=previous,
        conversation_proof=(
            inspect_conversation_evidence(root, now=NOW)
            if proof is None else proof
        ),
        now=NOW,
    )


def previous_from(result):
    return {
        "adaptive_sales_review": result["sales"],
        "adaptive_commercial_review": result["control"],
    }


def test_ops_initial_then_replay_persists_memory_without_emitting_duplicate_event(tmp_path):
    files = _test_sources(tmp_path)
    before = {str(f): f.read_bytes() for f in files}
    first = cycle(tmp_path)
    assert first["summary"]["available"] is True
    assert first["summary"]["status"] == "COMMERCIAL_EVIDENCE_REVIEW_HOLD"
    assert first["summary"]["active_dependency_gates"] >= 1
    assert first["summary"]["material_evidence_changed"] is True
    assert first["change_event"]["event_code"] == "COMMERCIAL_EVIDENCE_STATE_CHANGED"
    replay = cycle(tmp_path, previous_from(first))
    assert replay["summary"]["available"] is True
    assert replay["summary"]["material_evidence_changed"] is False
    assert replay["summary"]["operator_attention_due"] is False
    assert replay["summary"]["repeated_work_suppressed"] is True
    assert replay["change_event"] is None
    assert replay["control"]["transition"] == "UNCHANGED_COMMERCIAL_HOLD"
    assert all(f.read_bytes() == before[str(f)] for f in files)
    assert sorted(tmp_path.rglob("*.json")) == sorted(files)


def test_original_source_change_is_detected_but_not_promoted_to_reply(tmp_path):
    _test_sources(tmp_path)
    first = cycle(tmp_path)
    target = tmp_path / "runtime/conversation_recovery/latest.json"
    data = json.loads(target.read_text())
    data["owner_observation_annotation"] = "new producer version without authenticated reply"
    target.write_text(json.dumps(data))
    second = cycle(tmp_path, previous_from(first))
    assert second["summary"]["available"] is True
    assert second["summary"]["original_source_changed_without_proof"] is True
    assert second["summary"]["operator_attention_due"] is False
    assert second["summary"]["source_receipt_names_changed"] == ["conversation_recovery"]
    assert second["change_event"]["event_code"] == "ORIGINAL_SOURCE_RECEIPT_CHANGED_ONLY"
    assert second["change_event"]["owner_dispatch_executed"] is False
    assert second["sales"]["case_local_provider_authentication_attested"] is False
    third = cycle(tmp_path, previous_from(second))
    assert third["change_event"] is None


def test_failed_original_proof_stays_private_and_never_false_ready(tmp_path):
    _test_sources(tmp_path)
    truth = inspect_conversation_evidence(tmp_path, now=NOW)
    truth["execution_authority"] = "SEND"
    fail = cycle(tmp_path, proof=truth)
    assert fail["summary"]["status"] == "ADAPTIVE_COMMERCIAL_EVIDENCE_UNAVAILABLE"
    assert fail["summary"]["available"] is False
    assert fail["summary"]["outbound_authorized"] is False
    assert fail["summary"]["operator_attention_due"] is False
    assert fail["control"] is None
    assert fail["change_event"] is None
    assert "SEND" not in str(fail)


def test_prior_memory_survives_transient_source_unavailability(tmp_path):
    files = _test_sources(tmp_path)
    first = cycle(tmp_path)
    # Original offer-book input is mandatory. Its absence must not clear gates.
    book = tmp_path / "runtime/predictive_revenue/commercial_offer_book/latest.json"
    book.unlink()
    fail = cycle(tmp_path, previous_from(first))
    assert fail["summary"]["available"] is False
    assert fail["control"] == first["control"]
    assert fail["sales"] == first["sales"]
    assert fail["change_event"] is None
    assert fail["summary"]["outbound_authorized"] is False
    # Recovered owned producer data can be reevaluated with preserved checkpoint.
    assert book in files


def test_source_receipts_allowlisted_and_no_identifying_fields(tmp_path):
    _test_sources(tmp_path)
    hashes = source_receipts(tmp_path)
    assert len(hashes) == 10
    assert "conversation_recovery" in hashes
    assert set(hashes.values())
    assert all(len(value) == 64 for value in hashes.values())
    assert "private@" not in str(hashes)
    assert "synthetic-thread-1" not in str(hashes)


def test_ops_cycle_code_wiring_does_not_register_a_second_scheduler():
    path = Path("scripts/run_ops_control_cycle.py")
    code = path.read_text(encoding="utf-8")
    assert "observe_ops_adaptive_commercial(" in code
    assert '"adaptive_sales_review": adaptive["sales"]' in code
    assert '"adaptive_commercial_review": adaptive["control"]' in code
    assert '"adaptive_commercial_summary": adaptive["summary"]' in code
    assert '"adaptive_commercial_transitions.jsonl"' in code
    assert "systemctl enable empire-adaptive" not in code
    bridge = Path("empire_os/commercial_adaptive_ops_bridge.py").read_text()
    for bad in ("send_email(", "create_agent(", "requests.post(", "run_scheduler("):
        assert bad not in bridge
