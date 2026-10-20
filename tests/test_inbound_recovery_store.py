"""Signed callback and durable replay tests: no external provider, DB or network."""
from hashlib import sha256
import json
import time

import jwt
import pytest

from empire_os.inbound_provider_contract import InboundNumberRegistry, InboundNumberRoute
from empire_os.inbound_recovery_store import (
    OfflineRecoveryStore, ingest_signed_vonage_status_offline,
)
from empire_os.inbound_revenue_recovery import RecoveryEvent
from empire_os.inbound_signature_verification import (
    InvalidVoiceCallback, verify_vonage_voice_callback,
)

SECRET = "test-only-signature-secret-do-not-use-live-012345"
API_KEY = "test-account-123"
APP = "00000000-1111-2222-3333-444444444444"


def raw_callback(*, status="unanswered", did="+442012345678", call_id="call-1",
                 timestamp="2026-10-20T09:00:00+00:00"):
    return json.dumps(
        {"to": did, "uuid": call_id, "status": status, "timestamp": timestamp},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def sign(body: bytes, *, secret=SECRET, key=API_KEY, app=APP, jti="jti-1",
         issued=None, omit_hash=False):
    data = {
        "iss": "Vonage", "api_key": key, "application_id": app,
        "iat": int(time.time()) if issued is None else issued,
        "jti": jti,
    }
    if not omit_hash:
        data["payload_hash"] = sha256(body).hexdigest()
    return "Bearer " + jwt.encode(data, secret, algorithm="HS256")


def registry():
    return InboundNumberRegistry([
        InboundNumberRoute(
            tenant_id="tenant-a", e164_number="+442012345678",
            business_name="Acme", number_ownership_verified=True,
            inbound_enabled=True,
        ),
        InboundNumberRoute(
            tenant_id="tenant-b", e164_number="+442088888888",
            business_name="Other", number_ownership_verified=True,
            inbound_enabled=True,
        ),
    ])


def verify(body, token, **kwargs):
    return verify_vonage_voice_callback(
        token, body, signature_secret=SECRET, expected_api_key=API_KEY,
        expected_application_id=APP, **kwargs,
    )


def ingest(db, body, authorization):
    return ingest_signed_vonage_status_offline(
        body, authorization, store=db, registry=registry(),
        signature_secret=SECRET, expected_api_key=API_KEY,
        expected_application_id=APP,
    )


def test_valid_signed_callback_binds_api_key_and_application():
    raw = raw_callback()
    evidence = verify(raw, sign(raw))
    assert evidence.provider == "vonage"
    assert evidence.api_key == API_KEY
    assert evidence.application_id == APP
    assert evidence.payload_sha256 == sha256(raw).hexdigest()


@pytest.mark.parametrize("bad_token", ["", "Bearer", "Basic nope", "Bearer abc.def.bad", "Bearer x y"])
def test_invalid_or_missing_authorization_fails_closed(bad_token):
    with pytest.raises(InvalidVoiceCallback):
        verify(raw_callback(), bad_token)


def test_mutated_payload_or_wrong_secret_fails_closed():
    original = raw_callback()
    with pytest.raises(InvalidVoiceCallback, match="payload_hash"):
        verify(raw_callback(status="answered"), sign(original))
    with pytest.raises(InvalidVoiceCallback):
        verify(original, sign(original, secret="wrong-secret-not-the-configured-webhook-key"))


def test_api_key_application_and_hash_missing_rejected():
    original = raw_callback()
    with pytest.raises(InvalidVoiceCallback, match="api_key"):
        verify(original, sign(original, key="another-api-key"))
    with pytest.raises(InvalidVoiceCallback, match="application"):
        verify(original, sign(original, app="wrong-application"))
    with pytest.raises(InvalidVoiceCallback):
        verify(original, sign(original, omit_hash=True))


def test_old_token_rejected_by_freshness_check():
    original = raw_callback()
    with pytest.raises(InvalidVoiceCallback, match="freshness"):
        verify(original, sign(original, issued=int(time.time()) - 3600))


def test_non_json_object_and_oversize_body_rejected():
    data = b"[]"
    with pytest.raises(InvalidVoiceCallback, match="object"):
        verify(data, sign(data))
    with pytest.raises(InvalidVoiceCallback, match="payload"):
        verify(b"x" * 66000, sign(b"x" * 66000))


def test_signed_provider_intake_survives_database_restart(tmp_path):
    path = tmp_path / "recover.db"
    body = raw_callback()
    authorization = sign(body)
    with OfflineRecoveryStore(path) as store:
        assert ingest(store, body, authorization)
        assert not ingest(store, body, authorization)
        assert store.report("tenant-a")["missed_calls"] == 1
        assert store.report("tenant-b")["missed_calls"] == 0
    with OfflineRecoveryStore(path) as store:
        assert store.report("tenant-a")["missed_calls"] == 1
        assert not ingest(store, body, authorization)


def test_provider_event_retries_with_fresh_jti_remain_idempotent(tmp_path):
    body = raw_callback()
    with OfflineRecoveryStore(tmp_path / "calls.db") as store:
        assert ingest(store, body, sign(body, jti="first"))
        assert not ingest(store, body, sign(body, jti="second"))
        assert store.report("tenant-a")["calls_observed"] == 1


def test_signed_callback_does_not_inherit_untrusted_tenant_id(tmp_path):
    body = raw_callback()
    parsed = json.loads(body)
    parsed["tenant_id"] = "tenant-b"
    tampered = json.dumps(parsed).encode()
    with OfflineRecoveryStore(tmp_path / "calls.db") as store:
        with pytest.raises(ValueError, match="provider_tenant_mismatch"):
            ingest(store, tampered, sign(tampered))
        assert store.report("tenant-a")["calls_observed"] == 0
        assert store.report("tenant-b")["calls_observed"] == 0


def test_no_nonregistered_number_or_wrong_route_even_if_signed(tmp_path):
    body = raw_callback(did="+449999999999")
    with OfflineRecoveryStore(tmp_path / "calls.db") as store:
        with pytest.raises(ValueError, match="unregistered"):
            ingest(store, body, sign(body))
        assert store.report("tenant-a")["calls_observed"] == 0


def test_jti_conflict_raises_without_partial_commit(tmp_path):
    body = raw_callback(status="unanswered")
    different = raw_callback(status="answered")
    with OfflineRecoveryStore(tmp_path / "calls.db") as store:
        assert ingest(store, body, sign(body, jti="reused"))
        with pytest.raises(ValueError, match="conflicting_callback_jwt_replay"):
            ingest(store, different, sign(different, jti="reused"))
        assert store.report("tenant-a")["calls_observed"] == 1


def test_offline_storage_rejects_mutation_of_existing_event_id(tmp_path):
    with OfflineRecoveryStore(tmp_path / "calls.db") as store:
        original = RecoveryEvent(
            tenant_id="tenant-a", event_id="E-1", call_id="C-1",
            occurred_at="2026-10-20T09:00:00+00:00",
            kind="unanswered", origin="provider",
        )
        assert store.append_offline(original)
        assert not store.append_offline(original)
        with pytest.raises(ValueError, match="conflicting_duplicate"):
            store.append_offline(RecoveryEvent(
                tenant_id="tenant-a", event_id="E-1", call_id="C-2",
                occurred_at="2026-10-20T09:00:00+00:00",
                kind="unanswered", origin="provider",
            ))


def test_store_reports_tenant_and_synthetic_only(tmp_path):
    with OfflineRecoveryStore(tmp_path / "calls.db") as store:
        store.append_offline(RecoveryEvent(
            tenant_id="tenant-b", event_id="S-1", call_id="C-1",
            occurred_at="2026-10-20T09:00:00+00:00",
            kind="unanswered", origin="provider",
        ))
        store.append_offline(RecoveryEvent(
            tenant_id="tenant-a", event_id="S-1", call_id="C-1",
            occurred_at="2026-10-20T09:00:00+00:00",
            kind="unanswered", origin="provider",
        ))
        assert store.report("tenant-a")["calls_observed"] == 0
        assert store.report("tenant-b")["calls_observed"] == 0
