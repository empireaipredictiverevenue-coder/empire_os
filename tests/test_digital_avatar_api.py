from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.digital_avatar_api import create_digital_avatar_router


def client():
    app = FastAPI()
    app.include_router(create_digital_avatar_router())
    return TestClient(app)


def identity_payload():
    return {
        "avatar_id": "avatar-phil-v1",
        "owner_name": "Phil Livesley",
        "display_name": "Phil — Empire AI Digital Avatar",
        "organisation_name": "Empire AI",
        "disclosure_text": "I am Phil's authorised Empire AI Digital Avatar.",
        "owner_consent_evidence_ref": "consent:phil:avatar:v1",
    }


def session_payload(mode="shadow", disclosed=False):
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "provider": "provider-test",
        "mode": mode,
        "disclosure_announced": disclosed,
    }


def test_health_is_read_only_observe():
    response = client().get("/v1/digital-avatar/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["read_only"] is True
    assert body["speech_execution"] is False
    assert body["close_execution"] is False
    assert body["payment_execution"] is False
    assert body["execution_authority"] == "none"


def test_action_preview_cannot_speak_in_shadow():
    response = client().post(
        "/v1/digital-avatar/actions/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload("shadow", True),
            "action": "speak",
        },
    )
    assert response.status_code == 200
    decision = response.json()["decision"]
    assert decision["allowed"] is False
    assert "shadow_mode_cannot_speak" in decision["blockers"]
    assert "runtime_observe_only" in decision["blockers"]


def test_strategy_preview_uses_real_predictive_formula_contract():
    predictive = {
        "demand": 0.8,
        "quality": 0.9,
        "enrichment": 0.9,
        "omega_qualification": 0.8,
        "buyer_match": 0.75,
        "outreach": 0.7,
        "conversion": 0.6,
        "terms": 0.8,
        "payment": 0.9,
        "fulfilment": 0.95,
        "ltv_cents": 500000,
    }
    actions = [{
        "action_key": "present_verified_case_evidence",
        "probability_action_changes_outcome": 0.7,
        "incremental_revenue_if_changed_cents": 100000,
        "action_cost_cents": 0,
        "confidence": 0.9,
    }]

    response = client().post(
        "/v1/digital-avatar/strategy/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload(),
            "account_name": "Example Buyer",
            "objective": "qualify fit and agree next step",
            "proof_refs": ["evidence:case:7"],
            "commercial_terms_ref": "terms:product:approved:v1",
            "predictive_inputs": predictive,
            "action_candidates": actions,
        },
    )
    assert response.status_code == 200
    strategy = response.json()["strategy"]
    assert strategy["predictive_revenue"]["status"] == "AVAILABLE"
    assert strategy["next_best_action"]["action_key"] == (
        "present_verified_case_evidence"
    )
    assert strategy["execution_authority"] == "none"
    assert strategy["actual_revenue"] is False


def test_missing_ai_disclosure_is_rejected():
    bad_identity = identity_payload()
    bad_identity["disclosure_text"] = "I represent Phil."
    response = client().post(
        "/v1/digital-avatar/actions/preview",
        json={
            "identity": bad_identity,
            "session": session_payload(),
            "action": "prepare_response",
        },
    )
    assert response.status_code == 422
    assert "explicitly identify AI" in response.json()["detail"]


def test_shadow_meeting_preview_is_private_and_non_executing():
    response = client().post(
        "/v1/digital-avatar/meeting/shadow/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload("shadow", False),
            "observations": [{
                "meeting_id": "meeting-001",
                "external_meeting_id": "zoom-abc",
                "platform": "zoom",
                "provider_event_id": "evt-1",
                "kind": "transcript_turn",
                "occurred_at": "2026-10-02T16:00:00+00:00",
                "evidence_ref": "provider:zoom:evt-1",
                "speaker_ref": "buyer-1",
                "speaker_role": "buyer",
                "text": "Implementation timing is our biggest concern.",
                "is_final": True,
            }],
            "account_name": "Example Buyer",
            "objective": "qualify fit and agree next step",
            "proof_refs": ["evidence:case:7"],
            "commercial_terms_ref": "terms:approved:v1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["private_guidance_only"] is True
    assert body["meeting_transport_active"] is False
    assert body["speech_execution"] is False
    assert body["execution_authority"] == "none"
    assert body["state"]["latest_buyer_utterance"]["text"] == (
        "Implementation timing is our biggest concern."
    )


def test_shadow_api_surfaces_human_takeover_for_out_of_policy_close():
    response = client().post(
        "/v1/digital-avatar/meeting/shadow/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload("shadow", False),
            "observations": [],
            "account_name": "Example Buyer",
            "objective": "prepare commercial close",
            "proof_refs": ["evidence:case:7"],
            "commercial_terms_ref": "terms:pilot:v1",
            "commercial_policy": {
                "allowed_product_codes": ["predictive-revenue-pilot"],
                "approved_terms_refs": ["terms:pilot:v1"],
                "allowed_currencies": ["USD"],
                "max_discount_bps": 500,
                "max_contract_months": 3,
            },
            "close_proposal": {
                "product_code": "predictive-revenue-pilot",
                "list_price_cents": 500000,
                "proposed_price_cents": 450000,
                "currency": "USD",
                "contract_months": 1,
                "terms_ref": "terms:pilot:v1",
                "evidence_refs": ["pricing:pilot:v1"],
            },
        },
    )
    assert response.status_code == 200
    guidance = response.json()["guidance"]
    assert guidance["human_takeover_required"] is True
    assert guidance["commercial_authority"]["policy_eligible"] is False
    assert "discount_exceeds_delegated_limit" in (
        guidance["commercial_authority"]["blockers"]
    )


def test_recall_shadow_plan_preview_is_non_executing():
    response = client().post(
        "/v1/digital-avatar/providers/recall/shadow-plan/preview",
        json={
            "meeting_id": "meeting-001",
            "avatar_id": "avatar-phil-v1",
            "platform": "zoom",
            "bot_name": "Phil — Empire AI Digital Avatar",
            "meeting_url": "https://zoom.us/j/123456789",
            "realtime_webhook_url": (
                "https://empire-ai.co.uk/v1/providers/recall/realtime"
            ),
            "recording_consent_evidence_ref": "consent:meeting:001",
            "webhook_verification_evidence_ref": "config:recall-signing:v1",
            "join_at": "2026-10-03T10:00:00+01:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "recall"
    assert body["api_call_allowed"] is False
    assert body["live_join_execution"] is False
    assert body["execution_authority"] == "none"
    assert body["plan"]["speech_execution"] is False
    assert body["plan"]["request_body"]["recording_config"][
        "realtime_endpoints"
    ][0]["events"][0] == "transcript.data"


def test_turn_approval_preview_requires_human_and_blocks_speech():
    response = client().post(
        "/v1/digital-avatar/turns/approval/preview",
        json={
            "session": session_payload("copilot", True),
            "purpose": "answer",
            "text": "The approved pilot is available.",
            "claims": [{
                "text": "The approved pilot is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["catalog:pilot:v1"],
            }],
            "strategy_evidence_refs": ["strategy:meeting-001:v1"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_explicit_human_approval"] is True
    assert body["speech_execution_allowed"] is False
    assert body["execution_authority"] == "none"
    assert body["decision"]["ready_for_human_approval"] is True
    assert body["decision"]["speech_execution_allowed"] is False


def test_recall_event_preview_requires_verified_webhook():
    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {"id": "bot-123"},
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": "Need"}, {"text": "a"}, {"text": "demo"}],
            },
        },
    }
    response = client().post(
        "/v1/digital-avatar/providers/recall/event/preview",
        json={
            "meeting_id": "meeting-001",
            "platform": "zoom",
            "payload": payload,
            "received_at": "2026-10-02T18:00:00+00:00",
            "verified": False,
            "participant_roles": {"7": "buyer"},
        },
    )
    assert response.status_code == 422
    assert "unverified Recall event rejected" in response.json()["detail"]


def test_recall_event_preview_returns_non_persisted_observation():
    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {"id": "bot-123"},
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": "Need"}, {"text": "a"}, {"text": "demo"}],
            },
        },
    }
    response = client().post(
        "/v1/digital-avatar/providers/recall/event/preview",
        json={
            "meeting_id": "meeting-001",
            "platform": "zoom",
            "payload": payload,
            "received_at": "2026-10-02T18:00:00+00:00",
            "verified": True,
            "participant_roles": {"7": "buyer"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["webhook_event_verified"] is True
    assert body["persistence_performed"] is False
    assert body["meeting_action_execution"] is False
    assert body["execution_authority"] == "none"
    assert body["observation"]["text"] == "Need a demo"
    assert body["observation"]["speaker_role"] == "buyer"


def test_meeting_memory_preview_preserves_observed_turns_only():
    response = client().post(
        "/v1/digital-avatar/meeting/memory/preview",
        json={
            "session": session_payload("shadow", False),
            "observations": [{
                "meeting_id": "meeting-001",
                "external_meeting_id": "bot-123",
                "platform": "zoom",
                "provider_event_id": "event-1",
                "kind": "transcript_turn",
                "occurred_at": "2026-10-02T18:00:00+00:00",
                "evidence_ref": "evidence:1",
                "speaker_ref": "recall-participant:7",
                "speaker_name": "Buyer",
                "speaker_role": "buyer",
                "text": "Can we start next week?",
                "is_final": True,
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary_generated"] is False
    assert body["inference_performed"] is False
    assert body["persistence_performed"] is False
    assert body["memory"]["truth_class"] == "OBSERVED"
    assert body["memory"]["latest_buyer_utterance"]["text"] == (
        "Can we start next week?"
    )


def test_response_task_preview_is_private_and_non_speaking():
    response = client().post(
        "/v1/digital-avatar/meeting/response-task/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload("shadow", False),
            "observations": [{
                "meeting_id": "meeting-001",
                "external_meeting_id": "bot-123",
                "platform": "zoom",
                "provider_event_id": "event-1",
                "kind": "transcript_turn",
                "occurred_at": "2026-10-02T18:00:00+00:00",
                "evidence_ref": "meeting:turn:1",
                "speaker_ref": "recall-participant:7",
                "speaker_name": "Buyer",
                "speaker_role": "buyer",
                "text": "Can you prove the ROI?",
                "is_final": True,
            }],
            "account_name": "Example Buyer",
            "objective": "qualify fit and agree next step",
            "proof_refs": ["evidence:case:7"],
            "commercial_terms_ref": "terms:pilot:v1",
            "action_candidates": [{
                "action_key": "present_verified_case_evidence",
                "probability_action_changes_outcome": 0.7,
                "incremental_revenue_if_changed_cents": 100000,
                "action_cost_cents": 0,
                "confidence": 0.9,
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "COPILOT_PREVIEW"
    assert body["requires_human_approval"] is True
    assert body["speech_execution_allowed"] is False
    assert body["response_task"]["latest_buyer_utterance"] == "Can you prove the ROI?"


def test_recall_shadow_pipeline_preview_returns_memory_and_guidance():
    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {"id": "bot-123"},
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": "We"}, {"text": "need"}, {"text": "this"}],
            },
        },
    }
    predictive = {
        "demand": 0.8, "quality": 0.9, "enrichment": 0.9,
        "omega_qualification": 0.8, "buyer_match": 0.75,
        "outreach": 0.7, "conversion": 0.6, "terms": 0.8,
        "payment": 0.9, "fulfilment": 0.95, "ltv_cents": 500000,
    }

    actions = [{
        "action_key": "ask_implementation_deadline",
        "probability_action_changes_outcome": 0.6,
        "incremental_revenue_if_changed_cents": 100000,
        "action_cost_cents": 0,
        "confidence": 0.9,
    }]
    response = client().post(
        "/v1/digital-avatar/providers/recall/shadow-pipeline/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload("shadow", False),
            "platform": "zoom",
            "events": [{
                "payload": payload,
                "received_at": "2026-10-02T18:00:00+00:00",
                "verified": True,
            }],
            "participant_roles": {"7": "buyer"},
            "account_name": "Example Buyer",
            "objective": "qualify fit and agree next step",
            "proof_refs": ["evidence:case:7"],
            "commercial_terms_ref": "terms:pilot:v1",
            "predictive_inputs": predictive,
            "action_candidates": actions,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["persistence_performed"] is False
    assert body["speech_execution"] is False
    assert body["execution_authority"] == "none"
    assert body["meeting_memory"]["truth_class"] == "OBSERVED"
    assert body["meeting_memory"]["summary_generated"] is False
    assert body["meeting_memory"]["inference_performed"] is False
    assert body["guidance"]["private_to_owner"] is True
    assert body["guidance"]["recommended_action"]["action_key"] == (
        "ask_implementation_deadline"
    )
    assert body["response_task"]["recommended_action_key"] == (
        "ask_implementation_deadline"
    )
    assert body["response_task"]["requires_human_approval"] is True
    assert body["response_task"]["speech_execution_allowed"] is False


def test_copilot_handoff_preview_never_transmits():
    response = client().post(
        "/v1/digital-avatar/copilot/handoff/preview",
        json={
            "identity": identity_payload(),
            "session": session_payload("copilot", True),
            "purpose": "answer",
            "text": "The approved pilot is available.",
            "claims": [{
                "text": "The approved pilot is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["catalog:pilot:v1"],
            }],
            "strategy_evidence_refs": ["strategy:meeting-001:v1"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["human_approval_required"] is True
    assert body["transmission_performed"] is False
    assert body["speech_execution_allowed"] is False
    assert body["execution_authority"] == "none"
    assert body["handoff"]["ready_for_human_approval"] is True
    assert body["handoff"]["human_approval_recorded"] is False
    assert body["handoff"]["transmission_performed"] is False


def test_response_draft_validation_accepts_only_grounded_candidate():
    response = client().post(
        "/v1/digital-avatar/meeting/response-draft/validate",
        json={
            "identity": identity_payload(),
            "session": session_payload("shadow", False),
            "observations": [{
                "meeting_id": "meeting-001",
                "external_meeting_id": "bot-123",
                "platform": "zoom",
                "provider_event_id": "evt-1",
                "kind": "transcript_turn",
                "occurred_at": "2026-10-02T18:00:00+00:00",
                "evidence_ref": "conversation:turn:7",
                "speaker_ref": "buyer:7",
                "speaker_name": "Buyer",
                "speaker_role": "buyer",
                "text": "Can you show me proof?",
                "is_final": True,
            }],
            "account_name": "Example Buyer",
            "objective": "qualify fit and agree next step",
            "proof_refs": ["evidence:case:7"],
            "commercial_terms_ref": "terms:pilot:v1",
            "draft_payload": {
                "text": "Yes. I can show you the verified case evidence.",
                "claims": [{
                    "text": "Verified case evidence is available.",
                    "truth_class": "VERIFIED",
                    "evidence_refs": ["evidence:case:7"],
                }],
            },
            "provider_key": "test-provider",
            "source_ref": "draft:test:1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["draft_generated_here"] is False
    assert body["transmission_performed"] is False
    assert body["speech_execution_allowed"] is False
    assert body["draft"]["ready_for_human_review"] is True
    assert body["draft"]["execution_authority"] == "none"


def test_mode_transition_preview_requires_single_step_and_never_executes():
    response = client().post(
        "/v1/digital-avatar/mode-transition/preview",
        json={
            "session": session_payload("shadow", True),
            "target_mode": "copilot",
            "owner_approval_evidence_ref": "approval:owner:1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transition_execution_performed"] is False
    assert body["execution_authority"] == "none"
    assert body["decision"]["policy_eligible"] is True
    assert body["decision"]["execution_allowed"] is False
    assert body["decision"]["blockers"] == ["runtime_observe_only"]
