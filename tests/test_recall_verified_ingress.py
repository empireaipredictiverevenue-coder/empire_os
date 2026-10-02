import base64
import hashlib
import hmac
import json

import pytest

from empire_os.meeting_gateway import MeetingPlatform
from empire_os.recall_verified_ingress import (
    verify_and_normalize_recall_event,
    verify_bind_and_normalize_recall_event,
)


def signed_request(payload):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_test_123"
    timestamp = "1790964000"
    signed = f"{webhook_id}.{timestamp}.{raw}".encode("utf-8")
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
    }
    return secret, headers, raw


def transcript_payload():
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


def test_verified_ingress_verifies_before_normalizing():
    secret, headers, raw = signed_request(transcript_payload())
    result = verify_and_normalize_recall_event(
        secret=secret,
        headers=headers,
        raw_payload=raw,
        meeting_id="meeting-001",
        platform=MeetingPlatform.ZOOM,
        received_at="2026-10-02T18:00:00+00:00",
        participant_roles={"7": "buyer"},
    )
    assert result.processing_order == (
        "verify_signature",
        "parse_json",
        "normalize_event",
    )
    assert result.verification.verified is True
    assert result.observation.text == "Need proof"
    assert result.observation.speaker_role.value == "buyer"
    assert result.persistence_performed is False
    assert result.execution_authority == "none"


def test_tampered_body_is_rejected_before_normalization():
    secret, headers, _ = signed_request(transcript_payload())
    tampered = '{"event":"transcript.partial_data"}'
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_and_normalize_recall_event(
            secret=secret,
            headers=headers,
            raw_payload=tampered,
            meeting_id="meeting-001",
            platform=MeetingPlatform.ZOOM,
            received_at="2026-10-02T18:00:00+00:00",
        )


def test_verified_non_json_payload_is_rejected_after_signature_check():
    raw = "not-json"
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_json_bad"
    timestamp = "1790964001"
    signed = f"{webhook_id}.{timestamp}.{raw}".encode("utf-8")
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
    }
    with pytest.raises(ValueError, match="not valid JSON"):
        verify_and_normalize_recall_event(
            secret=secret,
            headers=headers,
            raw_payload=raw,
            meeting_id="meeting-001",
            platform=MeetingPlatform.ZOOM,
            received_at="2026-10-02T18:00:00+00:00",
        )


def test_bound_ingress_uses_signed_bot_metadata_for_empire_session():
    secret, headers, raw = signed_request(transcript_payload())
    result = verify_bind_and_normalize_recall_event(
        secret=secret,
        headers=headers,
        raw_payload=raw,
        received_at="2026-10-02T18:00:00+00:00",
        participant_roles={"7": "buyer"},
    )
    assert result.processing_order == (
        "verify_signature",
        "parse_json",
        "bind_signed_bot_metadata",
        "normalize_event",
    )
    assert result.binding.meeting_id == "meeting-001"
    assert result.binding.avatar_id == "avatar-phil-v1"
    assert result.binding.platform.value == "zoom"
    assert result.observation.meeting_id == "meeting-001"
    assert result.observation.external_meeting_id == "bot-123"
    assert result.execution_authority == "none"


def test_bound_ingress_rejects_signed_metadata_with_execution_authority():
    bad = transcript_payload()
    bad["data"]["bot"]["metadata"]["execution_authority"] = "close"
    secret, headers, raw = signed_request(bad)
    with pytest.raises(ValueError, match="no execution authority"):
        verify_bind_and_normalize_recall_event(
            secret=secret,
            headers=headers,
            raw_payload=raw,
            received_at="2026-10-02T18:00:00+00:00",
        )
