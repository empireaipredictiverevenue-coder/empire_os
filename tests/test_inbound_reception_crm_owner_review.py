"""Synthetic HTTP proof of EXISTING CRM tenant-authorized receptionist review.

No production credentials, live DB, outbound or external telephony; the
actual PostgresRevenueCrmRepository transport is separately regression-tested.
"""
from hashlib import sha256
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
import jwt
import pytest

from empire_os.inbound_provider_contract import InboundNumberRoute
from empire_os.inbound_reception_call_flow import InboundReceptionCallEngine
from empire_os.inbound_reception_voice_api import create_inbound_reception_voice_app
from empire_os.inbound_revenue_recovery import TenantReceptionProfile
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository, RevenueCrmTransportError

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
NUMBER_A = "+442090001234"
NUMBER_B = "+442090005678"
API = "https://synthetic.example.test/v1/inbound-reception/vonage/input"
REVIEW = "/v1/inbound-reception/crm-review/enquiries"
SECRET = "synthetic-inbound-voice-authorization-key-32bytes"
KEY = "synthetic-vonage-key"
APPLICATION = "synthetic-vonage-application"


def engine():
    return InboundReceptionCallEngine(
        routes=(
            InboundNumberRoute(
                tenant_id=A, e164_number=NUMBER_A,
                business_name="Alpha Roofing", number_ownership_verified=True,
                inbound_enabled=True,
            ),
            InboundNumberRoute(
                tenant_id=B, e164_number=NUMBER_B,
                business_name="Beta Dental", number_ownership_verified=True,
                inbound_enabled=True,
            ),
        ),
        profiles={
            A: TenantReceptionProfile(
                tenant_id=A, business_name="Alpha Roofing",
                services=("roof inspection", "gutter repair"),
            ),
            B: TenantReceptionProfile(
                tenant_id=B, business_name="Beta Dental",
                services=("teeth cleaning",),
            ),
        },
        event_url=API,
    )


def synthetic_owner_resolver(tenant=A, *, valid=True, fail=False, rows=None):
    # Synthetic tests only: production supplies the existing canonical
    # account + dedicated LOGIN resolver, never this fixture.
    repo = PostgresRevenueCrmRepository(
        "synthetic_dsn_not_connected", tenant_id=tenant,
        connect_factory=lambda _: None,
    )

    def preview_prospects(*, limit):
        assert limit == 1
        if fail:
            raise RevenueCrmTransportError("synthetic unavailable")
        return [{"tenant_id": tenant}] if rows is None else rows

    repo.prospects = preview_prospects

    def resolver(request):
        if request.headers.get("authorization") != "Bearer synthetic-owner-token":
            return None
        if not valid:
            return object()
        return AuthenticatedRevenueCrmRead(tenant_id=tenant, repository=repo)

    return resolver


def signed_post(client, *, number, call, utterance=None, nonce):
    body = {"to": number, "uuid": call}
    stage = "answer"
    if utterance is not None:
        stage = "input"
        body["speech"] = {"results": [
            {"text": utterance, "confidence": 0.99},
        ]}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    claims = {
        "iss": "Vonage", "api_key": KEY, "application_id": APPLICATION,
        "jti": nonce, "iat": int(datetime.now(timezone.utc).timestamp()),
        "payload_hash": sha256(raw).hexdigest(),
    }
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    response = client.post(
        "/v1/inbound-reception/vonage/" + stage, content=raw,
        headers={
            "authorization": "Bearer " + token,
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200
    return response.json()


def create_client(*, owner_tenant=A, owner_resolver=None,
                  review_enabled=True, voice_enabled=True):
    shared = engine()
    client = TestClient(create_inbound_reception_voice_app(
        engine=shared, signature_secret=SECRET,
        api_key=KEY, application_id=APPLICATION,
        enabled=voice_enabled,
        resolve_authenticated_crm_read=(
            owner_resolver if owner_resolver is not None
            else synthetic_owner_resolver(owner_tenant)
        ),
        crm_owner_review_enabled=review_enabled,
    ))
    return shared, client


def fill_one_consent(client, *, number=NUMBER_A, call="synthetic-call-11111111",
                     service="roof inspection", prefix="a"):
    steps = [None, "appointment", service, "morning", "yes you may contact me"]
    result = []
    for i, text in enumerate(steps):
        result = signed_post(
            client, number=number, call=call, utterance=text,
            nonce="synthetic-voice-jti-" + prefix + str(i),
        )
    assert [item["action"] for item in result] == ["talk"]


def read(client, *, auth="Bearer synthetic-owner-token", params=None, headers=None):
    h = dict(headers or {})
    if auth is not None:
        h["authorization"] = auth
    return client.get(REVIEW, headers=h, params=params)


def test_authenticated_owner_sees_consent_only_after_signed_call():
    shared, client = create_client()
    assert read(client).status_code == 200
    assert read(client).json()["enquiry_drafts_count"] == 0
    fill_one_consent(client)
    response = read(client)
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "AUTHENTICATED_READ_ONLY_PRIVATE_PREVIEW"
    assert result["enquiry_drafts_count"] == 1
    assert result["canonical_crm_receipts"] == 0
    assert result["crm_writes"] is False
    assert result["recovered_revenue_claimed"] is False
    assert result["verified_recovered_calls"] == 0
    assert result["durable_queue_verified"] is False
    item, = result["review_items"]
    assert item["tenant_id"] == A
    assert item["service_code"] == "roof_inspection"
    assert item["time_preference"] == "morning"
    assert item["status"] == "PENDING_HUMAN_REVIEW_NOT_SUBMITTED"
    assert item["authorized_to_contact"] is False
    assert item["caller_contact_identity_verified"] is False
    assert response.headers["cache-control"] == "no-store"
    assert "roof inspection" not in str(result["review_items"]).lower()
    assert len(shared.review_handoffs_for_tenant(A)) == 1
    # A second review does not create or promote another enquiry.
    assert read(client).json()["enquiry_drafts_count"] == 1


def test_read_other_business_sees_only_its_own_enquiries():
    shared, client = create_client(owner_tenant=B)
    fill_one_consent(client, prefix="a")
    result = read(client).json()
    assert result["enquiry_drafts_count"] == 0
    assert result["review_items"] == []
    assert len(shared.review_handoffs_for_tenant(A)) == 1
    assert len(shared.review_handoffs_for_tenant(B)) == 0


def test_signed_second_business_only_visible_to_own_tenant():
    _shared, client = create_client(owner_tenant=B)
    fill_one_consent(
        client, number=NUMBER_B,
        call="synthetic-call-22222222", service="teeth cleaning", prefix="b",
    )
    result = read(client).json()
    assert result["enquiry_drafts_count"] == 1
    assert result["review_items"][0]["tenant_id"] == B


def test_unauthed_and_incorrect_object_denied():
    _, client = create_client()
    assert read(client, auth=None).status_code == 401
    assert read(client, auth="Bearer guessed").status_code == 401
    _, client2 = create_client(owner_resolver=synthetic_owner_resolver(valid=False))
    assert read(client2).status_code == 503


def test_crm_private_review_disabled_by_default():
    eng = engine()
    client = TestClient(create_inbound_reception_voice_app(
        engine=eng, signature_secret=SECRET, api_key=KEY,
        application_id=APPLICATION,
        enabled=True,
        resolve_authenticated_crm_read=synthetic_owner_resolver(),
    ))
    assert read(client).status_code == 404


def test_cannot_enable_private_review_without_auth_and_running_voice_engine():
    eng = engine()
    with pytest.raises(ValueError, match="existing_crm_auth"):
        create_inbound_reception_voice_app(
            engine=eng, signature_secret=SECRET, api_key=KEY,
            application_id=APPLICATION, enabled=True,
            crm_owner_review_enabled=True,
        )
    with pytest.raises(ValueError, match="requires_enabled_voice"):
        create_inbound_reception_voice_app(
            engine=eng, signature_secret=SECRET, api_key=KEY,
            application_id=APPLICATION,
            enabled=False, crm_owner_review_enabled=True,
            resolve_authenticated_crm_read=synthetic_owner_resolver(),
        )


def test_caller_scope_query_cannot_select_tenant():
    _, client = create_client()
    assert read(client, params={"tenant_id": B}).status_code == 422
    assert read(client, headers={"x-tenant-id": B}).json()["enquiry_drafts_count"] == 0


def test_crm_unavailable_or_mismatched_tenant_rows_hold():
    _, bad = create_client(owner_resolver=synthetic_owner_resolver(fail=True))
    assert read(bad).status_code == 503
    _, swapped = create_client(
        owner_resolver=synthetic_owner_resolver(rows=[{"tenant_id": B}])
    )
    assert read(swapped).status_code == 503


def test_external_resolver_exception_no_identity_leak():
    def denied(_request):
        raise ValueError("private-test-token-should-never-appear")
    _, client = create_client(owner_resolver=denied)
    response = read(client)
    assert response.status_code == 503
    assert "private-test-token" not in response.text


def test_wrong_crm_repository_identity_rejected():
    repo = PostgresRevenueCrmRepository(
        "synthetic_not_connected", tenant_id=B,
        connect_factory=lambda _: None,
    )
    _, client = create_client(owner_resolver=lambda _r: AuthenticatedRevenueCrmRead(
        tenant_id=A, repository=repo,
    ))
    assert read(client).status_code == 503


def test_unknown_customer_account_returns_no_reception_queue():
    outside = "33333333-3333-4333-8333-333333333333"
    _, client = create_client(owner_tenant=outside)
    result = read(client)
    assert result.status_code == 200
    assert result.json()["status"] == "NO_RECEPTIONIST_TENANT_CONFIGURED"
    assert result.json()["review_items"] == []
    assert result.json()["canonical_crm_receipts"] == 0


def test_bad_signed_voice_callback_cannot_create_owner_review_item():
    shared, client = create_client()
    resp = client.post(
        "/v1/inbound-reception/vonage/answer",
        json={"to": NUMBER_A, "uuid": "fake-unsigned-call-12345678"},
    )
    assert resp.status_code == 401
    assert shared.review_handoffs_for_tenant(A) == ()
    assert read(client).json()["enquiry_drafts_count"] == 0


def test_existing_crm_reader_returns_empty_rows_after_verified_tenant_session():
    _, client = create_client(
        owner_resolver=synthetic_owner_resolver(rows=[]),
    )
    r = read(client)
    assert r.status_code == 200
    assert r.json()["enquiry_drafts_count"] == 0
    assert r.json()["crm_writes"] is False



def test_same_existing_offline_store_survives_restart_and_crm_owner_can_read(tmp_path):
    """Synthetic signed phone HTTP, real local disk SQLite, no EmpireDB writes."""
    from empire_os.inbound_recovery_store import OfflineRecoveryStore

    path = tmp_path / "existing-recovery-store.sqlite3"
    with OfflineRecoveryStore(path):
        pass

    # Separate short-lived connections per webhook/read, as a real HTTP
    # worker requires. SQLite connections cannot be shared across threads.
    def append_local(data):
        with OfflineRecoveryStore(path) as store:
            return store.append_reception_draft_offline(data)

    def read_local(tenant):
        with OfflineRecoveryStore(path, read_only=True) as store:
            return store.reception_drafts_for_tenant(tenant)

    eng = InboundReceptionCallEngine(
        routes=tuple(engine().registry._routes.values()),
        profiles=engine().profiles,
        event_url=API,
        on_consented_draft=append_local,
    )
    client = TestClient(create_inbound_reception_voice_app(
        engine=eng, signature_secret=SECRET, api_key=KEY,
        application_id=APPLICATION, enabled=True,
        resolve_authenticated_crm_read=synthetic_owner_resolver(A),
        crm_owner_review_enabled=True,
        load_offline_drafts=read_local,
    ))
    fill_one_consent(client, prefix="durable-a")
    assert read(client).status_code == 200
    assert read(client).json()["offline_staging_receipts_count"] == 1
    assert len(read_local(A)) == 1
    assert read_local(B) == ()

    # A brand new process-local phone controller, same pre-existing disk file.
    with OfflineRecoveryStore(path, read_only=True) as persisted:
        assert len(persisted.reception_drafts_for_tenant(A)) == 1
        fresh_client = TestClient(create_inbound_reception_voice_app(
            engine=engine(), signature_secret=SECRET, api_key=KEY,
            application_id=APPLICATION, enabled=True,
            resolve_authenticated_crm_read=synthetic_owner_resolver(A),
            crm_owner_review_enabled=True,
            load_offline_drafts=read_local,
        ))
        after_restart = read(fresh_client)
        assert after_restart.status_code == 200
        result = after_restart.json()
        assert result["enquiry_drafts_count"] == 1
        assert result["offline_staging_receipts_count"] == 1
        assert result["canonical_crm_receipts"] == 0
        assert result["durable_queue_verified"] is False
        assert result["crm_writes"] is False
        other_client = TestClient(create_inbound_reception_voice_app(
            engine=engine(), signature_secret=SECRET, api_key=KEY,
            application_id=APPLICATION, enabled=True,
            resolve_authenticated_crm_read=synthetic_owner_resolver(B),
            crm_owner_review_enabled=True,
            load_offline_drafts=read_local,
        ))
        assert read(other_client).json()["enquiry_drafts_count"] == 0


def test_offline_durable_replay_is_idempotent_and_conflict_held(tmp_path):
    from dataclasses import replace
    from empire_os.inbound_recovery_store import OfflineRecoveryStore
    from empire_os.inbound_reception_intake import draft_for_call

    data = draft_for_call(
        tenant_id=A, call_id="synthetic-call-11111111",
        kind="appointment", service="roof_inspection", window="morning",
    )
    path = tmp_path / "existing-recovery-store.sqlite3"
    with OfflineRecoveryStore(path) as repo:
        assert repo.append_reception_draft_offline(data) is True
        assert repo.append_reception_draft_offline(data) is False
        with pytest.raises(ValueError, match="conflicting_reception_draft"):
            repo.append_reception_draft_offline(replace(data, preferred_time_window="evening"))
        assert len(repo.reception_drafts_for_tenant(A)) == 1
    with OfflineRecoveryStore(path, read_only=True) as reader:
        assert reader.reception_drafts_for_tenant(A) == (data,)
        with pytest.raises(ValueError, match="offline_store_read_only"):
            reader.append_reception_draft_offline(data)


def test_offline_sink_failure_never_acknowledges_or_creates_phantom_lead(tmp_path):
    from empire_os.inbound_recovery_store import OfflineRecoveryStore
    path = tmp_path / "recovery.sqlite"
    with OfflineRecoveryStore(path) as prepared:
        pass
    with OfflineRecoveryStore(path, read_only=True) as reader:
        base = engine()
        shared = InboundReceptionCallEngine(
            routes=tuple(base.registry._routes.values()), profiles=base.profiles,
            event_url=API,
            on_consented_draft=reader.append_reception_draft_offline,
        )
        client = TestClient(create_inbound_reception_voice_app(
            engine=shared, signature_secret=SECRET, api_key=KEY,
            application_id=APPLICATION, enabled=True,
        ))
        steps = [None, "appointment", "roof inspection", "morning"]
        for i, utterance in enumerate(steps):
            signed_post(
                client, number=NUMBER_A, call="synthetic-call-11111111",
                utterance=utterance, nonce="failure-sink-jti-" + str(i),
            )
        data = {"to": NUMBER_A, "uuid": "synthetic-call-11111111",
                "speech": {"results": [{"text": "yes you may contact me", "confidence": 0.99}]}}
        raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        token = jwt.encode({
            "iss": "Vonage", "api_key": KEY, "application_id": APPLICATION,
            "jti": "failure-sink-final-jti",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "payload_hash": sha256(raw).hexdigest(),
        }, SECRET, algorithm="HS256")
        response = client.post(
            "/v1/inbound-reception/vonage/input", content=raw,
            headers={"authorization": "Bearer " + token,
                     "content-type": "application/json"},
        )
        assert response.status_code == 422
        assert shared.sessions["synthetic-call-11111111"].closed is False
        assert shared.sessions["synthetic-call-11111111"].intake_stage == "permission"
        assert shared.review_handoffs_for_tenant(A) == ()
        assert reader.reception_drafts_for_tenant(A) == ()


def test_offline_reader_wrong_tenant_result_is_not_silently_filtered():
    from empire_os.inbound_reception_intake import draft_for_call
    wrong = draft_for_call(
        tenant_id=B, call_id="synthetic-call-22222222",
        kind="appointment", service="teeth_cleaning", window="afternoon",
    )
    _, client = create_client(
        owner_resolver=synthetic_owner_resolver(A), review_enabled=False,
    )
    eng = engine()
    active = TestClient(create_inbound_reception_voice_app(
        engine=eng, signature_secret=SECRET, api_key=KEY,
        application_id=APPLICATION, enabled=True,
        resolve_authenticated_crm_read=synthetic_owner_resolver(A),
        crm_owner_review_enabled=True,
        load_offline_drafts=lambda _tenant: (wrong,),
    ))
    assert read(active).status_code == 503
