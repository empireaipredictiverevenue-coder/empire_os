"""Safe FAQ and controlled knowledge preview regression tests."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.inbound_recovery_api import create_inbound_recovery_router
from empire_os.inbound_tenant_knowledge import (
    KnowledgeFact, TenantKnowledgePack, answer_from_knowledge,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def fact(*, tenant="alpha", fact_id="f1", question="Do you install solar panels",
         answer="We install rooftop solar panels.",
         topic="services", approved=True, synthetic=False,
         reviewed=None, expires=None):
    return KnowledgeFact(
        tenant_id=tenant, fact_id=fact_id, question=question,
        answer=answer, source_ref="first-party-service-policy-v3",
        reviewed_by="client-operator-1",
        reviewed_at=(reviewed or NOW - timedelta(days=2)).isoformat(),
        expires_at=(expires or NOW + timedelta(days=30)).isoformat(),
        topic=topic, approved=approved, synthetic=synthetic,
    )


def pack(*items, tenant="alpha", active=True):
    return TenantKnowledgePack(
        tenant_id=tenant, business_name="Alpha Solar",
        version=3, activated=active, facts=tuple(items),
    )


def answer(facts, query="Do you install solar panels", **kw):
    return answer_from_knowledge(
        pack(*facts, **kw), query, as_of=NOW,
    )


def test_matching_approved_first_party_answer_is_cited():
    response = answer([fact()])
    assert response.status == "approved_fact"
    assert response.spoken_text.startswith("I am Alpha Solar's AI assistant.")
    assert response.evidence_refs == ("first-party-service-policy-v3",)
    assert response.pack_version == 3
    assert response.match_coverage == 1.0
    assert response.payment_authorized is False


def test_inactive_or_unapproved_facts_cannot_be_spoken():
    assert answer([fact()], active=False).status == "not_activated"
    assert answer([fact(approved=False)]).status == "insufficient_evidence"
    assert answer([fact(synthetic=True)]).status == "insufficient_evidence"


def test_stale_fact_is_rejected():
    old = fact(
        reviewed=NOW - timedelta(days=32),
        expires=NOW - timedelta(days=1),
    )
    assert answer([old]).status == "insufficient_evidence"


@pytest.mark.parametrize("topic", [
    "pricing", "availability", "booking_confirmation",
    "regulated_advice", "payment", "refund_decision",
])
def test_sensitive_topics_require_human_verification(topic):
    response = answer([fact(topic=topic)])
    assert response.status == "needs_human_review"
    assert response.fact_id is None
    assert "verify" in response.spoken_text
    assert response.booking_confirmed is False


def test_conflicting_equally_matching_facts_fail_closed():
    other = fact(fact_id="f2", answer="We maintain existing solar systems only.")
    result = answer([fact(), other])
    assert result.status == "ambiguous"
    assert not result.evidence_refs


def test_cross_tenant_fact_and_duplicate_fact_ids_rejected():
    with pytest.raises(ValueError, match="cross_tenant"):
        pack(fact(tenant="beta"))
    with pytest.raises(ValueError, match="duplicate"):
        pack(fact(), fact())


def test_expiration_and_review_window_strict():
    with pytest.raises(ValueError, match="review_window"):
        fact(expires=NOW + timedelta(days=365))
    with pytest.raises(ValueError, match="timezone"):
        fact(reviewed=datetime(2026, 10, 1, 9), expires=NOW)


def test_unknown_question_cannot_be_hallucinated():
    result = answer([fact()], query="Can you repair underground gas pipes")
    assert result.status == "insufficient_evidence"
    assert not result.evidence_refs


def test_low_information_question_requests_clarification():
    result = answer([fact()], query="What is it")
    assert result.status == "insufficient_evidence"
    assert "tell me more" in result.spoken_text


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN", "test-private-preview-only")
    app = FastAPI()
    app.include_router(create_inbound_recovery_router())
    return TestClient(app)


def preview(client, topic="services", *, intent="faq", approved=True):
    return client.post(
        "/v1/inbound-recovery/preview",
        headers={"x-empire-preview-token": "test-private-preview-only"},
        json={
            "tenant_id": "alpha", "business_name": "Alpha Solar",
            "intent": intent,
            "knowledge_preview": {
                "version": 1,
                "activated": True,
                "as_of": NOW.isoformat(),
                "question": "Do you install solar panels",
                "facts": [{
                    "fact_id": "f1",
                    "question": "Do you install solar panels",
                    "answer": "We install rooftop solar panels.",
                    "source_ref": "client-approved-FAQ-1",
                    "reviewed_by": "client-operator-1",
                    "reviewed_at": (NOW - timedelta(days=2)).isoformat(),
                    "expires_at": (NOW + timedelta(days=20)).isoformat(),
                    "topic": topic, "approved": approved,
                }],
            },
        },
    )


def test_preview_safe_approved_fact_is_clearly_a_simulation(client):
    result = preview(client)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["action"] == "faq_preview_approved_fact"
    assert payload["knowledge"]["simulated_not_provider_verified"] is True
    assert payload["knowledge"]["evidence_refs"] == ["client-approved-FAQ-1"]
    assert payload["provider_connected"] is False
    assert payload["booking_confirmed"] is False


def test_preview_sensitive_pricing_topic_must_abstain(client):
    result = preview(client, topic="pricing")
    assert result.status_code == 200
    assert result.json()["knowledge"]["status"] == "needs_human_review"
    assert not result.json()["knowledge"]["evidence_refs"]


def test_preview_does_not_override_emergency_or_optout(client):
    for intent in ("emergency", "stop"):
        result = preview(client, intent=intent)
        assert result.status_code == 200
        assert result.json()["knowledge"] is None
        assert result.json()["action"] in {"urgent_human_escalation", "honour_opt_out"}


def test_miscategorized_price_or_guaranteed_availability_is_blocked():
    for risky in ("£399 per month", "Your appointment is guaranteed available tomorrow"):
        response = answer([
            fact(topic="general", answer=risky),
        ])
        assert response.status == "needs_human_review"
        assert response.evidence_refs == ()


def test_live_answer_cannot_use_synthetic_even_if_approved():
    pack_simulated = pack(fact(synthetic=True))
    live = answer_from_knowledge(pack_simulated, "Do you install solar panels", as_of=NOW)
    simulated = answer_from_knowledge(
        pack_simulated, "Do you install solar panels", as_of=NOW, simulated=True
    )
    assert live.status == "insufficient_evidence"
    assert simulated.status == "approved_fact"
