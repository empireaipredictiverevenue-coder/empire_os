import base64
import hashlib
import hmac
import json

from empire_os.recall_shadow_ingest_worker import (
    process_verified_spool,
    route_verified_spool_record,
)
from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import VerifiedRecallEnvelope
from empire_os.recall_webhook_verification import verify_recall_request


def payload():
    return {
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
                "words": [{"text": "Need"}, {"text": "proof"}],
            },
        },
    }


def verified_envelope():
    raw = json.dumps(payload(), separators=(",", ":"), sort_keys=True).encode()
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_worker_1"
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


def test_spool_record_routes_to_correlated_observation(tmp_path):
    spool = FileRecallVerifiedSpool(tmp_path / "spool")
    receipt = spool.enqueue(verified_envelope())
    record = json.loads(
        (tmp_path / "spool" / f"{receipt.queue_id}.json").read_text()
    )
    routed = route_verified_spool_record(record)
    assert routed.meeting_id == "meeting-001"
    assert routed.avatar_id == "avatar-phil-v1"
    assert routed.platform.value == "zoom"
    assert routed.observation.text == "Need proof"
    assert routed.truth_class == "OBSERVED"
    assert routed.canonical_truth_written is False
    assert routed.execution_authority == "none"


def test_worker_emits_observation_and_removes_raw_spool(tmp_path):
    spool_root = tmp_path / "spool"
    observation_root = tmp_path / "observations"
    spool = FileRecallVerifiedSpool(spool_root)
    spool.enqueue(verified_envelope())

    result = process_verified_spool(
        spool_root=spool_root,
        observation_root=observation_root,
    )
    assert result["processed"] == 1
    assert result["failed"] == 0
    assert not list(spool_root.glob("*.json"))
    outputs = list(observation_root.glob("*.json"))
    assert len(outputs) == 1
    data = json.loads(outputs[0].read_text())
    assert data["meeting_id"] == "meeting-001"
    assert data["observation"]["text"] == "Need proof"


def test_forbidden_authority_metadata_fails_closed(tmp_path):
    item = payload()
    item["data"]["bot"]["metadata"]["execution_authority"] = "live"
    raw = json.dumps(item, separators=(",", ":"), sort_keys=True).encode()
    envelope = verified_envelope()
    record = {
        "schema_version": "empire.recall_verified_spool.v1",
        "queue_id": "queue-1",
        "verification": {
            **envelope.verification.as_dict(),
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
        },
        "received_at": "2026-10-02T18:00:00+00:00",
        "raw_payload_base64": base64.b64encode(raw).decode(),
    }
    try:
        route_verified_spool_record(record)
    except ValueError as exc:
        assert "forbidden authority" in str(exc)
    else:
        raise AssertionError("authority expansion must fail")
