"""Existing Conversation OS qualification → CRM is review-only without original proof."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_reply_qualification import review_crm_reply_qualification
from empire_os.revenue_crm_api import create_revenue_crm_router


NOW = datetime(2026, 10, 9, 20, 20, tzinfo=timezone.utc)


def stage3():
    return {
        "status": "CODE_PATH_CURRENT_ORIGINAL_EVIDENCE_PENDING",
        "execution_authority": "none",
        "review_only": True,
        "buyer_intent_verified": False,
        "original_provider_authentication_verified": False,
        "tenant_authority_verified": False,
        "canonical_contact_binding_verified": False,
    }


def prospect():
    return {
        "prospect_id": "fixture-prospect-1", "tenant_id": "fixture-tenant-a",
        "conversation_id": "fixture-conversation-1", "conversation_state": "engaged",
        "closer_case_id": "fixture-closer-1", "closer_state": "proposal_ready",
    }


def conversation():
    return {
        "id": "fixture-conversation-1", "tenant_id": "fixture-tenant-a",
        "prospect_id": "fixture-prospect-1", "channel": "email",
        "state": "engaged",
    }


def inbound(when=None):
    return {
        "conversation_id": "fixture-conversation-1",
        "direction": "inbound",
        "event_type": "transcript_segment",
        "provider_event_id": "fixture-provider-event-1",
        "occurred_at": (when or (NOW - timedelta(minutes=5))).isoformat(),
        "body_text": "PRIVATE BODY MUST NOT ESCAPE",
        "evidence": {
            "transcript_ref": "fixture:transcript:1",
            "evidence_ref": "fixture:provider:1",
            "qualification_signals": ["interest", "commercial_need", "decision_authority"],
            "private_contact": "private@fixture.example",
        },
    }


def assess(**overrides):
    data=dict(prospect=prospect(), conversation=conversation(),
              events=[inbound()], stage3_source_health=stage3(), now=NOW)
    data.update(overrides)
    return review_crm_reply_qualification(**data)


def test_positive_synthetic_timeline_stays_blocked_for_live_buyer_promotion():
    result=assess()
    assert result["status"]=="BLOCKED_ORIGINAL_BUYER_PROOF"
    assert result["qualification_fresh_for_review"] is True
    assert result["candidate_qualification_signals_unverified"] == [
        "commercial_need","decision_authority","interest"
    ]
    assert result["inbound_event_count"]==1
    assert result["crm_operator_handoff_authorized"] is False
    assert result["canonical_buyer_authenticated"] is False
    assert result["tenant_authority_verified"] is False
    assert result["execution_authority"]=="none"
    assert result["crm_mutation"] is False
    assert result["closer_case_mutation"] is False
    assert result["payment_execution"] is False
    rendered=json.dumps(result)
    assert "PRIVATE BODY" not in rendered
    assert "private@fixture.example" not in rendered
    assert "fixture-tenant-a" not in rendered


@pytest.mark.parametrize("mutator,expected",[
    ("wrong_conversation", "CRM_CONVERSATION_ID_MISMATCH"),
    ("wrong_prospect", "CRM_PROSPECT_IDENTITY_MISMATCH"),
    ("wrong_tenant", "CRM_TENANT_SCOPE_CONFLICT"),
    ("missing_tenant", "CRM_TENANT_SCOPE_UNAVAILABLE"),
    ("nonemail", "CRM_CONVERSATION_NOT_EMAIL"),
    ("duplicate", "DUPLICATE_INBOUND_PROVIDER_EVENT"),
    ("source_id_missing", "ORIGINAL_INBOUND_EVENT_ID_MISSING"),
    ("stale","QUALIFICATION_EVIDENCE_STALE_OR_INVALID"),
    ("future","QUALIFICATION_EVIDENCE_STALE_OR_INVALID"),
    ("mixed_events","QUALIFICATION_SOURCE_CONTRACT_INVALID"),
    ("no_events","inbound_response_not_observed"),
    ("no_source","STAGE3_SOURCE_INTEGRITY_UNVERIFIED"),
])
def test_fail_closed_on_mismatch_or_unverified_signal(mutator,expected):
    kw={}
    c=conversation()
    p=prospect()
    events=[inbound()]
    if mutator=="wrong_conversation": c["id"]="fixture-other-conv"
    if mutator=="wrong_prospect": c["prospect_id"]="fixture-other-prospect"
    if mutator=="wrong_tenant": c["tenant_id"]="fixture-other-tenant"
    if mutator=="missing_tenant": p["tenant_id"]=None
    if mutator=="nonemail": c["channel"]="sms"
    if mutator=="duplicate": events.append(inbound())
    if mutator=="source_id_missing": events[0].pop("provider_event_id")
    if mutator=="stale": events=[inbound(NOW-timedelta(days=4))]
    if mutator=="future": events=[inbound(NOW+timedelta(days=4))]
    if mutator=="mixed_events": events[0]["conversation_id"]="fixture-other-conv"
    if mutator=="no_events": events=[]
    if mutator=="no_source": kw["stage3_source_health"]=None
    result=assess(prospect=p,conversation=c,events=events,**kw)
    assert expected in result["blockers"]
    if mutator in ("wrong_conversation","wrong_prospect","wrong_tenant",
                   "missing_tenant","nonemail"):
        assert result["candidate_qualification_signals_unverified"] == []
        assert result["inbound_event_count"] == 0
    assert result["crm_operator_handoff_authorized"] is False
    assert result["buyer_intent_verified"] is False


@pytest.mark.parametrize("data", [
    [{"direction":"inbound"}]*201, "not a bounded list", [None]
])
def test_invalid_event_reader_data_is_rejected(data):
    with pytest.raises(ValueError):
        assess(events=data)


def test_untrusted_execution_claim_in_stage3_cannot_authorize():
    forged=stage3()
    forged["buyer_intent_verified"]=True
    forged["execution_authority"]="send"
    result=assess(stage3_source_health=forged)
    assert "STAGE3_SOURCE_INTEGRITY_UNVERIFIED" in result["blockers"]
    assert result["crm_operator_handoff_authorized"] is False


class CRMRepo:
    def prospect(self, prospect_id):
        return prospect() if prospect_id=="fixture-prospect-1" else None
    def prospects(self, *,limit):return [prospect()]
    def buyers(self, *,limit):return []


class ConversationRepo:
    def conversation(self, *,conversation_id):
        return conversation()
    def timeline(self, *,conversation_id,limit):
        return [inbound(NOW-timedelta(minutes=2))]


def api(root, conversations=None, crm=True):
    app=FastAPI()
    app.include_router(create_revenue_crm_router(
        CRMRepo() if crm else None,
        conversation_read_repository=conversations,
        evidence_root=root,
    ))
    return TestClient(app)


def test_crm_api_reads_canonical_timeline_and_denies_handoff(tmp_path):
    body=api(tmp_path, conversations=ConversationRepo()).get(
        "/v1/revenue-crm/prospects/fixture-prospect-1/reply-qualification-review"
    )
    assert body.status_code==200
    data=body.json()
    assert data["mode"]=="OBSERVE"
    assert data["inbound_event_count"]==1
    assert data["crm_operator_handoff_authorized"] is False
    assert "STAGE3_SOURCE_INTEGRITY_UNVERIFIED" in data["blockers"]
    assert data["outbound_sent"] is False
    assert data["crm_mutation"] is False
    assert "PRIVATE BODY" not in body.text


def test_crm_api_unavailable_conversation_reader_shows_actual_failure(tmp_path):
    result=api(tmp_path).get(
        "/v1/revenue-crm/prospects/fixture-prospect-1/reply-qualification-review"
    )
    assert result.status_code==200
    report=result.json()
    assert "CANONICAL_CONVERSATION_NOT_READABLE" in report["blockers"]
    assert report["inbound_event_count"]==0
    assert report["crm_operator_handoff_authorized"] is False


def test_crm_api_prospect_lookup_and_repository_gates(tmp_path):
    assert api(tmp_path).get(
        "/v1/revenue-crm/prospects/unknown/reply-qualification-review"
    ).status_code==404
    result=api(tmp_path,crm=False).get(
        "/v1/revenue-crm/prospects/fixture-prospect-1/reply-qualification-review"
    )
    assert result.status_code==503
    assert result.json()["detail"]=="revenue_crm_repository_not_activated"


def test_crm_api_connection_failure_is_sanitized(tmp_path):
    class Fail:
        def conversation(self, *,conversation_id):raise RuntimeError(
            "password=<PRIVATE> DB credentials leaked"
        )
    result=api(tmp_path,conversations=Fail()).get(
        "/v1/revenue-crm/prospects/fixture-prospect-1/reply-qualification-review"
    )
    assert result.status_code==503
    assert result.json()["detail"]=="canonical_conversation_read_unavailable"
    assert "password" not in result.text
