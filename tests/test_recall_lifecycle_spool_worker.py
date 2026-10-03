import base64
import hashlib
import hmac
import json

from empire_os.recall_lifecycle_spool_worker import (
    build_lifecycle_record_from_spool,
    materialize_lifecycle_record,
)
from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import VerifiedRecallEnvelope
from empire_os.recall_webhook_verification import verify_recall_request


def envelope(code="in_call_recording"):
    payload = {
        "event": f"bot.{code}",
        "data": {
            "data": {
                "code": code,
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
    secret = "whsec_" + base64.b64encode(key).decode()
    webhook_id = "msg_lifecycle_1"
    timestamp = "1790964000"
    signed = webhook_id.encode() + b"." + timestamp.encode() + b"." + raw
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode()
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


def spooled(tmp_path, code="in_call_recording"):
    root = tmp_path / "status"
    receipt = FileRecallVerifiedSpool(root).enqueue(envelope(code))
    return root / f"{receipt.queue_id}.json"


def test_verified_status_spool_materializes_lifecycle(tmp_path):
    record = build_lifecycle_record_from_spool(
        spool_path=spooled(tmp_path),
    )
    assert record.truth_class == "VERIFIED"
    assert record.lifecycle["status_code"] == "in_call_recording"
    assert record.lifecycle["joined_meeting"] is True
    assert record.lifecycle["recording_active"] is True
    assert record.polling_performed is False
    assert record.commercial_truth_written is False
    assert record.execution_authority == "none"


def test_lifecycle_materialization_is_idempotent(tmp_path):
    source = spooled(tmp_path, "in_waiting_room")
    root = tmp_path / "lifecycle"
    first = materialize_lifecycle_record(
        spool_path=source,
        output_root=root,
    )
    second = materialize_lifecycle_record(
        spool_path=source,
        output_root=root,
    )
    assert first == second
    assert len(list(root.glob("*.json"))) == 1
    assert oct(first.stat().st_mode & 0o777) == "0o600"
