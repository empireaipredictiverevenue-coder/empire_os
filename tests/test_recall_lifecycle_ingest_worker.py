import base64
import hashlib
import hmac
import json

from empire_os.recall_lifecycle_ingest_worker import (
    process_verified_lifecycle_spool,
    route_verified_lifecycle_spool_record,
)
from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import VerifiedRecallEnvelope
from empire_os.recall_webhook_verification import verify_recall_request


def lifecycle_payload(code="in_call_recording", updated_at="2026-10-02T18:00:00+00:00"):
    return {
        "event": f"bot.{code}",
        "data": {
            "data": {
                "code": code,
                "sub_code": None,
                "updated_at": updated_at,
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


def verified_envelope(payload=None, webhook_id="msg_lifecycle_1"):
    value = payload or lifecycle_payload()
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
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


def test_lifecycle_spool_routes_as_verified_state_not_transcript(tmp_path):
    spool = FileRecallVerifiedSpool(tmp_path / "spool")
    receipt = spool.enqueue(verified_envelope())
    record = json.loads(
        (tmp_path / "spool" / f"{receipt.queue_id}.json").read_text()
    )
    routed = route_verified_lifecycle_spool_record(record)
    assert routed.lifecycle.status_code == "in_call_recording"
    assert routed.lifecycle.binding.meeting_id == "meeting-001"
    assert routed.truth_class == "VERIFIED"
    assert routed.transcript_evidence is False
    assert routed.predictive_revenue_input is False
    assert routed.execution_authority == "none"


def test_lifecycle_worker_writes_event_and_latest_snapshot(tmp_path):
    spool_root = tmp_path / "spool"
    event_root = tmp_path / "events"
    latest_root = tmp_path / "latest"
    FileRecallVerifiedSpool(spool_root).enqueue(verified_envelope())

    result = process_verified_lifecycle_spool(
        spool_root=spool_root,
        event_root=event_root,
        latest_root=latest_root,
    )
    assert result["processed"] == 1
    assert result["failed"] == 0
    assert result["meetings"] == ["meeting-001"]
    assert result["transcript_evidence_written"] is False
    assert result["predictive_revenue_input_written"] is False
    assert len(list(event_root.glob("*.json"))) == 1
    latest = json.loads((latest_root / "meeting-001.json").read_text())
    assert latest["lifecycle"]["recording_active"] is True
    assert latest["execution_authority"] == "none"


def test_non_shadow_lifecycle_binding_fails_closed(tmp_path):
    payload = lifecycle_payload()
    payload["data"]["bot"]["metadata"]["empire_mode"] = "close"
    spool = FileRecallVerifiedSpool(tmp_path / "spool")
    receipt = spool.enqueue(verified_envelope(payload))
    record = json.loads(
        (tmp_path / "spool" / f"{receipt.queue_id}.json").read_text()
    )
    try:
        route_verified_lifecycle_spool_record(record)
    except ValueError as exc:
        assert "not SHADOW mode" in str(exc)
    else:
        raise AssertionError("non-shadow lifecycle must fail")


def test_older_lifecycle_event_cannot_overwrite_newer_latest(tmp_path):
    spool_root = tmp_path / "spool"
    event_root = tmp_path / "events"
    latest_root = tmp_path / "latest"
    spool = FileRecallVerifiedSpool(spool_root)

    newer = lifecycle_payload(
        "in_call_recording",
        updated_at="2026-10-02T18:05:00+00:00",
    )
    spool.enqueue(
        verified_envelope(newer, webhook_id="msg_lifecycle_newer")
    )
    first = process_verified_lifecycle_spool(
        spool_root=spool_root,
        event_root=event_root,
        latest_root=latest_root,
    )
    assert first["processed"] == 1

    older = lifecycle_payload(
        "in_waiting_room",
        updated_at="2026-10-02T18:00:00+00:00",
    )
    spool.enqueue(
        verified_envelope(older, webhook_id="msg_lifecycle_older")
    )
    second = process_verified_lifecycle_spool(
        spool_root=spool_root,
        event_root=event_root,
        latest_root=latest_root,
    )
    assert second["processed"] == 1
    assert len(list(event_root.glob("*.json"))) == 2

    latest = json.loads(
        (latest_root / "meeting-001.json").read_text()
    )
    assert latest["lifecycle"]["status_code"] == "in_call_recording"
    assert latest["lifecycle"]["updated_at"] == (
        "2026-10-02T18:05:00+00:00"
    )


def test_out_of_order_lifecycle_event_does_not_overwrite_newer_latest(tmp_path):
    spool_root = tmp_path / "spool"
    event_root = tmp_path / "events"
    latest_root = tmp_path / "latest"

    newer = lifecycle_payload("in_call_recording")
    newer["data"]["data"]["updated_at"] = "2026-10-02T18:05:00+00:00"
    FileRecallVerifiedSpool(spool_root).enqueue(verified_envelope(newer))
    first = process_verified_lifecycle_spool(
        spool_root=spool_root,
        event_root=event_root,
        latest_root=latest_root,
    )
    assert first["processed"] == 1

    older = lifecycle_payload("in_waiting_room")
    older["data"]["data"]["updated_at"] = "2026-10-02T18:01:00+00:00"
    old_envelope = verified_envelope(older)
    old_record = old_envelope.verification
    # Force a distinct webhook identity so it is a distinct signed event.
    raw = old_envelope.raw_payload
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_lifecycle_older"
    timestamp = "1790964060"
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
    FileRecallVerifiedSpool(spool_root).enqueue(
        VerifiedRecallEnvelope(
            raw_payload=raw,
            headers=headers,
            verification=verification,
            received_at="2026-10-02T18:01:00+00:00",
        )
    )

    second = process_verified_lifecycle_spool(
        spool_root=spool_root,
        event_root=event_root,
        latest_root=latest_root,
    )
    assert second["processed"] == 1
    latest = json.loads((latest_root / "meeting-001.json").read_text())
    assert latest["lifecycle"]["status_code"] == "in_call_recording"
    assert latest["lifecycle"]["updated_at"] == "2026-10-02T18:05:00+00:00"
