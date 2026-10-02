import base64
import hashlib
import hmac

from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import VerifiedRecallEnvelope
from empire_os.recall_webhook_verification import verify_recall_request


def envelope(raw=b'{"event":"transcript.data"}'):
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_spool_1"
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


def test_verified_envelope_is_atomically_spooled(tmp_path):
    spool = FileRecallVerifiedSpool(tmp_path / "recall")
    receipt = spool.enqueue(envelope())
    assert receipt.queued is True
    assert receipt.duplicate is False
    assert receipt.canonical_truth_written is False

    files = list((tmp_path / "recall").glob("*.json"))
    assert len(files) == 1
    assert oct(files[0].stat().st_mode & 0o777) == "0o600"
    assert oct((tmp_path / "recall").stat().st_mode & 0o777) == "0o700"


def test_duplicate_webhook_is_idempotent(tmp_path):
    spool = FileRecallVerifiedSpool(tmp_path / "recall")
    first = spool.enqueue(envelope())
    second = spool.enqueue(envelope())
    assert first.queue_id == second.queue_id
    assert second.duplicate is True
    assert len(list((tmp_path / "recall").glob("*.json"))) == 1


def test_hash_mismatch_is_rejected(tmp_path):
    item = envelope()
    broken = VerifiedRecallEnvelope(
        raw_payload=b"tampered",
        headers=item.headers,
        verification=item.verification,
        received_at=item.received_at,
    )
    spool = FileRecallVerifiedSpool(tmp_path / "recall")
    try:
        spool.enqueue(broken)
    except ValueError as exc:
        assert "payload hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered verified envelope must fail")


def test_payload_limit_is_enforced(tmp_path):
    spool = FileRecallVerifiedSpool(
        tmp_path / "recall",
        max_payload_bytes=8,
    )
    try:
        spool.enqueue(envelope())
    except ValueError as exc:
        assert "exceeds spool limit" in str(exc)
    else:
        raise AssertionError("oversize verified payload must fail")
