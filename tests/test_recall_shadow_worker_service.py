import base64
import hashlib
import hmac
import json

import empire_os.recall_shadow_worker_service as worker
from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.meeting_gateway import MeetingSpeakerRole
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    save_recall_shadow_session,
)
from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import VerifiedRecallEnvelope
from empire_os.recall_webhook_verification import verify_recall_request


def make_envelope():
    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {
                "id": "bot-123",
                "metadata": {
                    "empire_meeting_id": "meeting-001",
                    "empire_avatar_id": "avatar-phil-v1",
                    "empire_platform": "zoom",
                    "empire_mode": "shadow",
                    "execution_authority": "none",
                },
            },
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": "Hello"}],
            },
        },
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_worker_service"
    timestamp = "1790964000"
    signed = webhook_id.encode() + b"." + timestamp.encode() + b"." + raw
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
    }
    verification = verify_recall_request(
        secret=secret,
        headers=headers,
        raw_payload=raw,
    )
    return VerifiedRecallEnvelope(
        raw_payload=raw,
        headers=headers,
        verification=verification,
        received_at="2026-10-02T18:00:00+00:00",
    )


def test_run_once_processes_verified_spool(monkeypatch, tmp_path):
    spool_root = tmp_path / "spool"
    observation_root = tmp_path / "observations"
    FileRecallVerifiedSpool(spool_root).enqueue(make_envelope())

    monkeypatch.setattr(worker, "SPOOL_ROOT", spool_root)
    monkeypatch.setattr(worker, "OBSERVATION_ROOT", observation_root)
    monkeypatch.setattr(worker, "SESSION_ROOT", tmp_path / "sessions")
    monkeypatch.setattr(worker, "GUIDANCE_ROOT", tmp_path / "guidance")
    monkeypatch.setattr(worker, "STATUS_SPOOL_ROOT", tmp_path / "status")
    monkeypatch.setattr(worker, "LIFECYCLE_ROOT", tmp_path / "lifecycle")
    monkeypatch.setattr(worker, "LIFECYCLE_LATEST_ROOT", tmp_path / "lifecycle_latest")
    monkeypatch.setattr(worker, "RUNTIME_STATE_ROOT", tmp_path / "runtime_state")
    monkeypatch.setattr(worker, "MEETING_STATE_ROOT", tmp_path / "meeting_state")
    monkeypatch.setattr(worker, "MAX_ITEMS", 10)

    result = worker.run_once()
    assert result["processed"] == 1
    assert result["failed"] == 0
    assert len(list(observation_root.glob("*.json"))) == 1


def make_manifest():
    return RecallShadowSessionManifest(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        session=AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        recording_consent_evidence_ref="consent:meeting:001",
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


def test_run_once_refreshes_private_guidance(monkeypatch, tmp_path):
    spool_root = tmp_path / "spool"
    observation_root = tmp_path / "observations"
    session_root = tmp_path / "sessions"
    guidance_root = tmp_path / "guidance"

    FileRecallVerifiedSpool(spool_root).enqueue(make_envelope())
    save_recall_shadow_session(
        root=session_root,
        manifest=make_manifest(),
    )

    monkeypatch.setattr(worker, "SPOOL_ROOT", spool_root)
    monkeypatch.setattr(worker, "OBSERVATION_ROOT", observation_root)
    monkeypatch.setattr(worker, "SESSION_ROOT", session_root)
    monkeypatch.setattr(worker, "GUIDANCE_ROOT", guidance_root)
    monkeypatch.setattr(worker, "STATUS_SPOOL_ROOT", tmp_path / "status")
    monkeypatch.setattr(worker, "LIFECYCLE_ROOT", tmp_path / "lifecycle")
    monkeypatch.setattr(worker, "LIFECYCLE_LATEST_ROOT", tmp_path / "lifecycle_latest")
    monkeypatch.setattr(worker, "RUNTIME_STATE_ROOT", tmp_path / "runtime_state")
    monkeypatch.setattr(worker, "MEETING_STATE_ROOT", tmp_path / "meeting_state")
    monkeypatch.setattr(worker, "MAX_ITEMS", 10)

    result = worker.run_once()
    assert result["processed"] == 1
    assert result["guidance_refreshed"] == 1
    assert result["guidance_failed"] == 0
    snapshot = json.loads(
        (guidance_root / "meeting-001.json").read_text()
    )
    assert snapshot["private_to_owner"] is True
    assert snapshot["speech_execution"] is False
    assert snapshot["response_task"]["requires_human_approval"] is True
    assert result["meeting_state_refreshed"] == 1
    state = json.loads(
        (tmp_path / "meeting_state" / "meeting-001.json").read_text()
    )
    assert state["latest_buyer_utterance"]["text"] == "Hello"
    assert state["private_to_owner"] is True
    assert state["speech_execution"] is False
    assert state["execution_authority"] == "none"


def make_lifecycle_envelope():
    payload = {
        "event": "bot.in_call_recording",
        "data": {
            "data": {
                "code": "in_call_recording",
                "sub_code": None,
                "updated_at": "2026-10-02T18:00:00+00:00",
            },
            "bot": {
                "id": "bot-123",
                "metadata": {
                    "empire_meeting_id": "meeting-001",
                    "empire_avatar_id": "avatar-phil-v1",
                    "empire_platform": "zoom",
                    "empire_mode": "shadow",
                    "execution_authority": "none",
                },
            },
        },
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_lifecycle_worker"
    timestamp = "1790964000"
    signed = webhook_id.encode() + b"." + timestamp.encode() + b"." + raw
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
    }
    verification = verify_recall_request(
        secret=secret,
        headers=headers,
        raw_payload=raw,
    )
    return VerifiedRecallEnvelope(
        raw_payload=raw,
        headers=headers,
        verification=verification,
        received_at="2026-10-02T18:00:00+00:00",
    )


def test_run_once_processes_lifecycle_spool(monkeypatch, tmp_path):
    status_root = tmp_path / "status"
    lifecycle_root = tmp_path / "lifecycle"
    FileRecallVerifiedSpool(status_root).enqueue(make_lifecycle_envelope())

    monkeypatch.setattr(worker, "SPOOL_ROOT", tmp_path / "spool")
    monkeypatch.setattr(worker, "OBSERVATION_ROOT", tmp_path / "observations")
    monkeypatch.setattr(worker, "SESSION_ROOT", tmp_path / "sessions")
    monkeypatch.setattr(worker, "GUIDANCE_ROOT", tmp_path / "guidance")
    monkeypatch.setattr(worker, "STATUS_SPOOL_ROOT", status_root)
    monkeypatch.setattr(worker, "LIFECYCLE_ROOT", lifecycle_root)
    monkeypatch.setattr(worker, "LIFECYCLE_LATEST_ROOT", tmp_path / "lifecycle_latest")
    monkeypatch.setattr(worker, "RUNTIME_STATE_ROOT", tmp_path / "runtime_state")
    monkeypatch.setattr(worker, "MEETING_STATE_ROOT", tmp_path / "meeting_state")
    monkeypatch.setattr(worker, "MAX_ITEMS", 10)

    result = worker.run_once()
    assert result["processed"] == 0
    assert result["lifecycle_processed"] == 1
    assert result["lifecycle_failed"] == 0
    assert result["polling_performed"] is False
    files = list(lifecycle_root.glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["truth_class"] == "VERIFIED"
    assert record["lifecycle"]["status_code"] == "in_call_recording"
    assert record["lifecycle"]["recording_active"] is True
    assert result["runtime_state_refreshed"] == 1
    assert result["runtime_state_failed"] == 0
    runtime_state = json.loads(
        (tmp_path / "runtime_state" / "meeting-001.json").read_text()
    )
    assert runtime_state["status_code"] == "in_call_recording"
    assert runtime_state["recording_active"] is True
    assert runtime_state["speech_execution"] is False
    assert runtime_state["execution_authority"] == "none"
    assert result["meeting_state_refreshed"] == 1
    state = json.loads(
        (tmp_path / "meeting_state" / "meeting-001.json").read_text()
    )
    assert state["lifecycle_status"] == "in_call_recording"
    assert state["recording_active"] is True
    assert "private_guidance_not_available" in state["blockers"]
