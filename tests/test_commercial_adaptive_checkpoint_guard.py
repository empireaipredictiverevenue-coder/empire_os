"""Privacy-first checkpoint fallback when original source packets become unavailable."""
from __future__ import annotations

from copy import deepcopy
import json
from datetime import datetime, timezone

from empire_os.commercial_adaptive_checkpoint_guard import (
    recover_safe_adaptive_checkpoints,
)
from empire_os.commercial_adaptive_ops_bridge import observe_ops_adaptive_commercial
from empire_os.conversation_control_operational_truth import inspect_conversation_evidence
from empire_os.commercial_adaptive_intelligence_control import _digest as commercial_digest
from empire_os.commercial_sales_director_adaptive_review import _digest as sales_digest
from test_commercial_adaptive_intelligence_cli import _test_sources

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def inputs(tmp_path):
    _test_sources(tmp_path)
    p = inspect_conversation_evidence(tmp_path, now=NOW)
    result = observe_ops_adaptive_commercial(
        root=tmp_path, previous_ops_snapshot={}, conversation_proof=p, now=NOW,
    )
    return result["sales"], result["control"]


def test_trusted_checkpoint_recovers_only_schema_minimal_memory(tmp_path):
    sales, commercial = inputs(tmp_path)
    compact_sales, compact_control = recover_safe_adaptive_checkpoints(sales, commercial)
    assert compact_sales["evidence_semantic_hash"] == sales["evidence_semantic_hash"]
    assert compact_control["decision_signature"] == commercial["decision_signature"]
    assert "plain_language_reason" not in compact_sales
    assert "active_dependency_gates" not in compact_control
    assert "recommended_parallel_reviews_not_dispatched" not in compact_control
    assert compact_sales["outbound_authorized"] is False
    assert compact_control["payment_execution"] is False


def test_unknown_or_sensitive_top_level_fields_never_survive(tmp_path):
    s, c = inputs(tmp_path)
    s["contact_email"] = "private@example.invalid"
    c["private_organisation"] = "Private Ltd"
    safe_s, safe_c = recover_safe_adaptive_checkpoints(s, c)
    assert safe_s is not None and safe_c is not None
    assert "private@" not in json.dumps(safe_s)
    assert "Private Ltd" not in json.dumps(safe_c)


def test_nested_semantic_contact_injection_rejected_even_with_new_digest(tmp_path):
    s, c = inputs(tmp_path)
    s["evidence_semantic_state"]["buyer_email"] = "private@example.invalid"
    s["evidence_semantic_hash"] = sales_digest(s["evidence_semantic_state"])
    c["decision_signature_data"]["original_reply_semantic"] = s["evidence_semantic_hash"]
    c["decision_signature"] = commercial_digest(c["decision_signature_data"])
    assert recover_safe_adaptive_checkpoints(s, c) == (None, None)


def test_distribution_state_contact_injection_rejected_even_after_checksum_update(tmp_path):
    s, c = inputs(tmp_path)
    states = c["decision_signature_data"]["distribution_states"]
    states["private@example.invalid"] = states.pop("conversion")
    c["decision_signature"] = commercial_digest(c["decision_signature_data"])
    assert recover_safe_adaptive_checkpoints(s, c) == (None, None)


def test_forged_no_holds_or_future_revenue_authority_rejected(tmp_path):
    s, c = inputs(tmp_path)
    c["payment_execution"] = True
    assert recover_safe_adaptive_checkpoints(s, c) == (None, None)
    s, c = inputs(tmp_path)
    s["execution_authority"] = "SEND"
    assert recover_safe_adaptive_checkpoints(s, c) == (None, None)


def test_not_a_valid_prior_packet_returns_empty(tmp_path):
    s, c = inputs(tmp_path)
    assert recover_safe_adaptive_checkpoints(None, c) == (None, None)
    assert recover_safe_adaptive_checkpoints(s, None) == (None, None)
    assert recover_safe_adaptive_checkpoints("raw_message_body", c) == (None, None)


def test_checkpoint_recovery_does_not_modify_original_packets(tmp_path):
    s, c = inputs(tmp_path)
    before_s, before_c = deepcopy(s), deepcopy(c)
    recover_safe_adaptive_checkpoints(s, c)
    assert s == before_s
    assert c == before_c
