"""Reuses original warm buyer owner, without inventing payable terms or sales."""
from datetime import datetime, timezone
import copy

import pytest
from empire_os.commercial_buyer_source_health import inspect_original_warm_partner_closing

NOW = datetime(2026, 10, 27, 13, tzinfo=timezone.utc)


def registry():
    return {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "mode": "OBSERVE", "execution_authority": "NONE",
        "founder_actions_are_draft_only": True,
        "outbound_authorized": False, "outbound_sent": False,
        "relationships": [
            {"entity_key": "leadbank", "company": "LeadBank",
             "stage": "AWAITING_BUYER", "last_inbound_at": NOW.isoformat(),
             "gmail_thread_ids": ["private"], "private_email": "secret@example.invalid"},
            {"entity_key": "lead-smart", "company": "Lead Smart",
             "stage": "INBOUND_REVIEW_REQUIRED"},
        ],
        "warm_business_action_queue": [
            {"entity_key": "leadbank"},
            {"entity_key": "lead-smart"},
        ],
        "partner_pilot_readiness_queue": [{
            "entity_key": "leadbank",
            "activation_stage": "WAITING_BUYER_BUYBOX",
            "current_next_partner_task": "WAIT_CURRENT_BUYBOX_AND_SOURCE_APPROVAL",
            "two_way_gmail_thread_observed": True,
            "gate_count_verified": 0,
        }],
    }


def load(monkeypatch, value, status="CURRENT_REGISTRY_REVIEW_ONLY"):
    from empire_os import buyer_qualification_evidence_bridge as original
    monkeypatch.setattr(original, "load_registry", lambda root, *, now: (value, status))


def test_warm_buyer_owner_queue_is_not_an_accepted_payer(monkeypatch, tmp_path):
    source = registry()
    original = copy.deepcopy(source)
    load(monkeypatch, source)
    out = inspect_original_warm_partner_closing(tmp_path, now=NOW)
    assert source == original
    assert out["status"] == "EXISTING_WARM_BUYERS_REQUIRE_OWNER_TERMS_PROOF"
    assert out["warm_relationship_count"] == 2
    assert out["verified_recognized_revenue_cents"] is None
    assert out["confirmed_buyer_payable_agreement_count"] is None
    assert out["agent_tasks_created"] is False
    assert "secret@" not in str(out) and "private" not in str(out)
    assert out["warm_reviews"][0]["original_owner_verified_pilot_gate_count"] == 0
    assert out["warm_reviews"][0]["two_way_thread_original_owner_reported"] is True
    assert all(item["written_payable_terms_independently_verified_by_review"] is False
               for item in out["warm_reviews"])


def test_missing_or_partial_registry_stays_a_hold(monkeypatch, tmp_path):
    load(monkeypatch, {}, "UNVERIFIED_MISSING_OR_UNSAFE_REGISTRY")
    r = inspect_original_warm_partner_closing(tmp_path, now=NOW)
    assert r["warm_relationship_count"] is None
    assert r["verified_recognized_revenue_cents"] is None
    assert r["status"] == "ORIGINAL_FOUNDER_REGISTRY_REVIEW_HOLD"


@pytest.mark.parametrize("field,value", [
    ("outbound_authorized", True),
    ("outbound_sent", True),
    ("founder_actions_are_draft_only", False),
])
def test_untrusted_registry_cannot_promote_buyer(monkeypatch, tmp_path, field, value):
    source = registry()
    source[field] = value
    load(monkeypatch, source)
    result = inspect_original_warm_partner_closing(tmp_path, now=NOW)
    assert result["status"] == "ORIGINAL_FOUNDER_REGISTRY_REVIEW_HOLD"
    assert result["warm_relationship_count"] is None


def test_ambiguous_entity_identity_fails_closed(monkeypatch, tmp_path):
    source = registry()
    source["relationships"].append(copy.deepcopy(source["relationships"][0]))
    load(monkeypatch, source)
    result = inspect_original_warm_partner_closing(tmp_path, now=NOW)
    assert result["status"] == "ORIGINAL_FOUNDER_REGISTRY_REVIEW_HOLD"


def test_unknown_manual_action_never_promotes_to_send(monkeypatch, tmp_path):
    source = registry()
    source["partner_pilot_readiness_queue"][0]["current_next_partner_task"] = "SEND_EMAIL_AUTOMATICALLY"
    load(monkeypatch, source)
    result = inspect_original_warm_partner_closing(tmp_path, now=NOW)
    assert result["warm_reviews"][0]["original_next_founder_task"] == "REVIEW_ORIGINAL_OWNER_EVIDENCE_NO_REPEAT"
    assert result["outbound_authorized"] is False


def test_invalid_clock_rejected(monkeypatch, tmp_path):
    load(monkeypatch, registry())
    with pytest.raises(ValueError):
        inspect_original_warm_partner_closing(tmp_path, now=datetime(2026, 10, 27))
