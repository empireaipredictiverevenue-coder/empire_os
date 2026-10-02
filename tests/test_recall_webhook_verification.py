import base64
import hashlib
import hmac

import pytest

from empire_os.recall_webhook_verification import verify_recall_request


def secret():
    key = b"0123456789abcdef0123456789abcdef"
    return "whsec_" + base64.b64encode(key).decode("ascii"), key


def headers_for(raw):
    value, key = secret()
    webhook_id = "msg_test_123"
    timestamp = "1790964000"
    signed = f"{webhook_id}.{timestamp}.{raw}".encode("utf-8")
    sig = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    return value, {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{sig}",
    }


def test_valid_recall_hmac_is_verified():
    raw = '{"event":"transcript.data"}'
    value, headers = headers_for(raw)
    evidence = verify_recall_request(
        secret=value,
        headers=headers,
        raw_payload=raw,
    )
    assert evidence.verified is True
    assert evidence.signature_version == "v1"
    assert evidence.payload_sha256 == hashlib.sha256(raw.encode()).hexdigest()
    assert evidence.evidence_ref.startswith("recall-verification:msg_test_123:")


def test_payload_mutation_breaks_signature():
    raw = '{"event":"transcript.data"}'
    value, headers = headers_for(raw)
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_recall_request(
            secret=value,
            headers=headers,
            raw_payload='{"event":"transcript.partial_data"}',
        )


def test_missing_headers_fail_closed():
    value, _ = secret()
    with pytest.raises(ValueError, match="verification headers missing"):
        verify_recall_request(
            secret=value,
            headers={},
            raw_payload="{}",
        )


def test_invalid_secret_fails_closed():
    with pytest.raises(ValueError, match="secret missing or invalid"):
        verify_recall_request(
            secret="not-a-recall-secret",
            headers={},
            raw_payload="{}",
        )


def test_multiple_signatures_accept_matching_v1():
    raw = '{"event":"participant_events.join"}'
    value, headers = headers_for(raw)
    good = headers["webhook-signature"]
    headers["webhook-signature"] = "v2,AAAA " + good
    evidence = verify_recall_request(
        secret=value,
        headers=headers,
        raw_payload=raw,
    )
    assert evidence.verified is True


def test_header_matching_is_case_insensitive():
    raw = '{"event":"participant_events.leave"}'
    value, headers = headers_for(raw)
    mixed = {
        "Webhook-Id": headers["webhook-id"],
        "Webhook-Timestamp": headers["webhook-timestamp"],
        "Webhook-Signature": headers["webhook-signature"],
    }
    evidence = verify_recall_request(
        secret=value,
        headers=mixed,
        raw_payload=raw,
    )
    assert evidence.verified is True
