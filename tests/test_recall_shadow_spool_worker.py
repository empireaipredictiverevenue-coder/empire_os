import base64
import hashlib
import hmac
import json

import pytest

from empire_os.recall_shadow_spool_worker import (
    build_observed_record_from_spool,
    materialize_observed_record,
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
    raw = json.dumps(
        payload(),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
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


def spooled(tmp_path):
    root = tmp_path / "spool"
    receipt = FileRecallVerifiedSpool(root).enqueue(verified_envelope())
    return root / f"{receipt.queue_id}.json"


def test_verified_spool_becomes_observed_meeting_record(tmp_path):
    item = build_observed_record_from_spool(
        spool_path=spooled(tmp_path),
        participant_roles={"7": "buyer"},
    )
    assert item.avatar_id == "avatar-phil-v1"
    assert item.binding_truth_class == "VERIFIED"
    assert item.truth_class == "OBSERVED"
    assert item.observation["meeting_id"] == "meeting-001"
    assert item.observation["speaker_role"] == "buyer"
    assert item.observation["text"] == "Need proof"
    assert item.inference_performed is False
    assert item.commercial_truth_written is False
    assert item.execution_authority == "none"


def test_materialization_is_idempotent_and_private(tmp_path):
    source = spooled(tmp_path)
    out = tmp_path / "observed"
    first = materialize_observed_record(
        spool_path=source,
        output_root=out,
    )
    second = materialize_observed_record(
        spool_path=source,
        output_root=out,
    )
    assert first == second
    assert len(list(out.glob("*.json"))) == 1
    assert oct(first.stat().st_mode & 0o777) == "0o600"


def test_tampered_spool_payload_is_rejected(tmp_path):
    source = spooled(tmp_path)
    record = json.loads(source.read_text())
    record["raw_payload_base64"] = base64.b64encode(b"tampered").decode()
    source.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="payload hash mismatch"):
        build_observed_record_from_spool(spool_path=source)
