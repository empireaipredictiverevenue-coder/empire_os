import base64
import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import empire_os.recall_shadow_worker_service as worker
from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.meeting_gateway import MeetingSpeakerRole
from empire_os.recall_shadow_activation import prepare_recall_shadow_activation
from empire_os.recall_shadow_join import RecallShadowJoinApproval
from empire_os.recall_shadow_session import save_recall_shadow_session
from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import (
    create_recall_lifecycle_webhook_router,
    create_recall_webhook_router,
)


def activation():
    return prepare_recall_shadow_activation(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        meeting_id="meeting-001",
        platform="zoom",
        meeting_url="https://zoom.us/j/123456789",
        bot_name="Phil — Empire AI Digital Avatar",
        public_realtime_url=(
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        owner_join_approval=RecallShadowJoinApproval(
            meeting_id="meeting-001",
            approved_by="Phil Livesley",
            approval_evidence_ref="approval:shadow:meeting-001:v1",
            approved_at="2026-10-02T18:00:00+00:00",
            expires_at="2026-10-02T20:00:00+00:00",
        ),
        region="eu-central-1",
        now="2026-10-02T18:30:00+00:00",
        recording_consent_evidence_ref="consent:meeting:001",
        webhook_verification_evidence_ref="config:recall-signing:v1",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        predictive_inputs={
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
        },
        action_candidates=({
            "action_key": "ask_implementation_deadline",
            "probability_action_changes_outcome": 0.6,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 0,
            "confidence": 0.9,
        },),
        participant_roles={
            "recall-participant:7": MeetingSpeakerRole.BUYER,
        },
    )


def signed_headers(secret, webhook_id, timestamp, raw):
    key = base64.b64decode(secret[len("whsec_"):])
    signed = webhook_id.encode() + b"." + timestamp.encode() + b"." + raw
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    return {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
        "content-type": "application/json",
    }


def test_full_shadow_path_to_private_response_task(monkeypatch, tmp_path):
    packet = activation()
    session_root = tmp_path / "sessions"
    spool_root = tmp_path / "spool"
    observation_root = tmp_path / "observations"
    guidance_root = tmp_path / "guidance"
    save_recall_shadow_session(
        root=session_root,
        manifest=packet.manifest,
    )

    secret = "whsec_" + base64.b64encode(
        b"0123456789abcdef0123456789abcdef"
    ).decode("ascii")
    spool = FileRecallVerifiedSpool(spool_root)
    app = FastAPI()
    app.include_router(
        create_recall_webhook_router(
            secret_provider=lambda: secret,
            verified_envelope_sink=spool.enqueue,
        )
    )

    metadata = packet.bot_plan.request_body["metadata"]
    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {"id": "bot-e2e-1", "metadata": metadata},
            "transcript": {"id": "transcript-e2e-1"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [
                    {"text": "Can"},
                    {"text": "you"},
                    {"text": "deploy"},
                    {"text": "this"},
                    {"text": "quickly?"},
                ],
            },
        },
    }
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    response = TestClient(app).post(
        "/v1/providers/recall/realtime",
        content=raw,
        headers=signed_headers(
            secret,
            "msg_e2e_1",
            "1790964000",
            raw,
        ),
    )
    assert response.status_code == 200
    assert response.json()["processed_inline"] is False

    monkeypatch.setattr(worker, "SPOOL_ROOT", spool_root)
    monkeypatch.setattr(worker, "OBSERVATION_ROOT", observation_root)
    monkeypatch.setattr(worker, "SESSION_ROOT", session_root)
    monkeypatch.setattr(worker, "GUIDANCE_ROOT", guidance_root)
    monkeypatch.setattr(worker, "MAX_ITEMS", 20)

    result = worker.run_once()
    assert result["processed"] == 1
    assert result["guidance_refreshed"] == 1
    assert result["guidance_failed"] == 0

    snapshot = json.loads(
        (guidance_root / "meeting-001.json").read_text()
    )
    latest = snapshot["guidance"]["latest_buyer_utterance"]
    assert latest["text"] == "Can you deploy this quickly?"
    assert latest["speaker_role"] == "buyer"
    assert snapshot["guidance"]["recommended_action"]["action_key"] == (
        "ask_implementation_deadline"
    )
    assert snapshot["response_task"]["requires_human_approval"] is True
    assert snapshot["response_task"]["speech_execution_allowed"] is False
    assert snapshot["execution_authority"] == "none"


def post_signed(client, *, path, secret, payload, webhook_id, timestamp):
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return client.post(
        path,
        content=raw,
        headers=signed_headers(secret, webhook_id, timestamp, raw),
    )


def test_full_shadow_lifecycle_and_transcript_to_founder_state(monkeypatch, tmp_path):
    packet = activation()
    session_root = tmp_path / "sessions"
    realtime_spool = tmp_path / "realtime_spool"
    lifecycle_spool = tmp_path / "lifecycle_spool"
    observation_root = tmp_path / "observations"
    lifecycle_root = tmp_path / "lifecycle"
    lifecycle_latest_root = tmp_path / "lifecycle_latest"
    runtime_state_root = tmp_path / "runtime_state"
    guidance_root = tmp_path / "guidance"
    meeting_state_root = tmp_path / "meeting_state"
    save_recall_shadow_session(root=session_root, manifest=packet.manifest)

    secret = "whsec_" + base64.b64encode(
        b"0123456789abcdef0123456789abcdef"
    ).decode("ascii")
    app = FastAPI()
    app.include_router(
        create_recall_webhook_router(
            secret_provider=lambda: secret,
            verified_envelope_sink=FileRecallVerifiedSpool(
                realtime_spool
            ).enqueue,
        )
    )
    app.include_router(
        create_recall_lifecycle_webhook_router(
            secret_provider=lambda: secret,
            verified_envelope_sink=FileRecallVerifiedSpool(
                lifecycle_spool
            ).enqueue,
        )
    )
    client = TestClient(app)
    metadata = packet.bot_plan.request_body["metadata"]

    for index, (code, updated_at) in enumerate((
        ("in_waiting_room", "2026-10-02T18:01:00+00:00"),
        ("in_call_recording", "2026-10-02T18:02:00+00:00"),
    ), start=1):
        lifecycle_payload = {
            "event": f"bot.{code}",
            "data": {
                "data": {
                    "code": code,
                    "sub_code": None,
                    "updated_at": updated_at,
                },
                "bot": {
                    "id": "bot-e2e-state",
                    "metadata": metadata,
                },
            },
        }
        response = post_signed(
            client,
            path="/v1/providers/recall/lifecycle",
            secret=secret,
            payload=lifecycle_payload,
            webhook_id=f"msg_lifecycle_e2e_{index}",
            timestamp=str(1790964000 + index),
        )
        assert response.status_code == 200
        assert response.json()["processed_inline"] is False

    transcript_payload = {
        "event": "transcript.data",
        "data": {
            "bot": {
                "id": "bot-e2e-state",
                "metadata": metadata,
            },
            "transcript": {"id": "transcript-e2e-state"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [
                    {"text": "Can"},
                    {"text": "you"},
                    {"text": "deploy"},
                    {"text": "this"},
                    {"text": "quickly?"},
                ],
            },
        },
    }
    response = post_signed(
        client,
        path="/v1/providers/recall/realtime",
        secret=secret,
        payload=transcript_payload,
        webhook_id="msg_transcript_e2e_state",
        timestamp="1790964010",
    )
    assert response.status_code == 200

    monkeypatch.setattr(worker, "SPOOL_ROOT", realtime_spool)
    monkeypatch.setattr(worker, "STATUS_SPOOL_ROOT", lifecycle_spool)
    monkeypatch.setattr(worker, "OBSERVATION_ROOT", observation_root)
    monkeypatch.setattr(worker, "LIFECYCLE_ROOT", lifecycle_root)
    monkeypatch.setattr(
        worker,
        "LIFECYCLE_LATEST_ROOT",
        lifecycle_latest_root,
    )
    monkeypatch.setattr(worker, "RUNTIME_STATE_ROOT", runtime_state_root)
    monkeypatch.setattr(worker, "SESSION_ROOT", session_root)
    monkeypatch.setattr(worker, "GUIDANCE_ROOT", guidance_root)
    monkeypatch.setattr(worker, "MEETING_STATE_ROOT", meeting_state_root)
    monkeypatch.setattr(worker, "MAX_ITEMS", 20)

    result = worker.run_once()
    assert result["processed"] == 1
    assert result["lifecycle_processed"] == 2
    assert result["guidance_refreshed"] == 1
    assert result["runtime_state_refreshed"] == 1
    assert result["meeting_state_refreshed"] == 1

    state = json.loads(
        (meeting_state_root / "meeting-001.json").read_text()
    )
    assert state["lifecycle_status"] == "in_call_recording"
    assert state["joined_meeting"] is True
    assert state["recording_active"] is True
    assert state["latest_buyer_utterance"]["text"] == (
        "Can you deploy this quickly?"
    )
    assert state["recommended_action"]["action_key"] == (
        "ask_implementation_deadline"
    )
    assert state["response_task"]["requires_human_approval"] is True
    assert state["human_takeover_required"] is False
    assert state["private_to_owner"] is True
    assert state["speech_execution"] is False
    assert state["chat_execution"] is False
    assert state["commercial_execution"] is False
    assert state["execution_authority"] == "none"
