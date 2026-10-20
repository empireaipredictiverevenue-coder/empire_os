"""External IAM vault: fake Scaleway APIs, no cloud access or real secrets."""
import base64
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from empire_os.inbound_calendar_oauth_boundary import (
    CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ,
)
from empire_os.inbound_calendar_token_vault import CalendarCredential
from empire_os.inbound_google_calendar_adapter import CalendarVerificationError
from empire_os.inbound_scaleway_calendar_vault import (
    ScalewaySecretManagerHTTP, ScalewaySecretManagerCalendarVault,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
CAL = "chosen-calendar@example.org"
ACCOUNT = "existing-google-owner"
SECRET_ID = "00000000-0000-0000-0000-000000000099"
NOW = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)
SCOPES = frozenset({CALENDAR_LIST_READ, CALENDAR_FREEBUSY, EVENTS_READ})


class FakeIAMGateway:
    """In-memory fixed secret; mimics immutable enabled latest-version policy."""
    def __init__(self):
        self.versions = {}
        self.calls = []

    def access_latest(self, secret_id):
        self.calls.append(("GET", secret_id))
        return self.versions.get(secret_id)

    def add_version(self, secret_id, payload):
        self.calls.append(("POST", secret_id))
        self.versions[secret_id] = payload
        return len(self.calls)


def vault(gateway=None):
    source = gateway or FakeIAMGateway()
    return ScalewaySecretManagerCalendarVault(source, approved_secret_ids={
        (TENANT, CAL, ACCOUNT): SECRET_ID,
    }), source


def credential(*, tenant=TENANT, cal=CAL, account=ACCOUNT,
               refresh="fixture-refresh-secret"):
    return CalendarCredential(
        tenant_id=tenant, calendar_id=cal, provider_account_ref=account,
        google_client_id="fixture-google-client",
        access_token="fixture-access-secret", refresh_token=refresh,
        scopes=SCOPES, issued_at=NOW, expires_at=NOW + timedelta(minutes=20),
        customer_approved=True, provider_grant_verified=True,
    )


def test_verified_remote_write_get_rotate_revocation_and_zero_token_metadata():
    manager, gateway = vault()
    record = credential()
    with manager:
        manager.put_verified_offline(record, at=NOW)
        assert b"fixture-refresh-secret" in gateway.versions[SECRET_ID]  # mock ONLY
        assert manager.get_active(tenant_id=TENANT, calendar_id=CAL,
                                  provider_account_ref=ACCOUNT) == record
        rotated = credential(refresh="rotated-test-token")
        manager.put_verified_offline(rotated, at=NOW)
        assert manager.get_active(tenant_id=TENANT, calendar_id=CAL,
                                  provider_account_ref=ACCOUNT).refresh_token == "rotated-test-token"
        assert manager.revoke_local(
            tenant_id=TENANT, calendar_id=CAL,
            provider_account_ref=ACCOUNT, at=NOW)
        assert b"rotated-test-token" not in gateway.versions[SECRET_ID]
        assert manager.status(tenant_id=TENANT)["known_active_credentials"] is None
        assert manager.status(tenant_id=TENANT)["tokens_returned"] is False
        with pytest.raises(CalendarVerificationError, match="revoked"):
            manager.get_active(tenant_id=TENANT, calendar_id=CAL,
                               provider_account_ref=ACCOUNT)
        assert not manager.revoke_local(
            tenant_id=TENANT, calendar_id=CAL,
            provider_account_ref=ACCOUNT, at=NOW)
        with pytest.raises(CalendarVerificationError, match="revoked"):
            manager.put_verified_offline(record, at=NOW)


def test_wrong_tenant_never_performs_remote_access():
    manager, remote = vault()
    with pytest.raises(CalendarVerificationError, match="preprovisioned"):
        manager.get_active(tenant_id=OTHER, calendar_id=CAL, provider_account_ref=ACCOUNT)
    with pytest.raises(CalendarVerificationError, match="preprovisioned"):
        manager.put_verified_offline(credential(tenant=OTHER), at=NOW)
    with pytest.raises(CalendarVerificationError, match="preprovisioned"):
        manager.revoke_local(tenant_id=TENANT, calendar_id="wrong-calendar",
                             provider_account_ref=ACCOUNT, at=NOW)
    assert remote.calls == []


def test_duplicate_secret_id_for_two_customers_is_rejected():
    with pytest.raises(ValueError, match="shared"):
        ScalewaySecretManagerCalendarVault(FakeIAMGateway(), approved_secret_ids={
            (TENANT, CAL, ACCOUNT): SECRET_ID,
            (OTHER, CAL, ACCOUNT): SECRET_ID,
        })


def test_malicious_or_wrong_identity_secret_data_denied():
    manager, gateway = vault()
    manager.put_verified_offline(credential(), at=NOW)
    doc = json.loads(gateway.versions[SECRET_ID])
    doc["credential"]["tenant_id"] = OTHER
    gateway.versions[SECRET_ID] = json.dumps(doc).encode()
    with pytest.raises(CalendarVerificationError, match="cross_tenant"):
        manager.get_active(tenant_id=TENANT, calendar_id=CAL, provider_account_ref=ACCOUNT)
    with pytest.raises(CalendarVerificationError, match="conflict"):
        manager.put_verified_offline(credential(), at=NOW)


@pytest.mark.parametrize("invalid", [
    {}, {(TENANT, CAL, ACCOUNT): "not-a-uuid"},
    {(TENANT, CAL, ACCOUNT): "00000000-0000-0000-0000-000000000099",
     (OTHER, CAL, ACCOUNT): "00000000-0000-0000-0000-000000000099"},
])
def test_unapproved_mapping_denied(invalid):
    with pytest.raises((ValueError, CalendarVerificationError)):
        ScalewaySecretManagerCalendarVault(FakeIAMGateway(), approved_secret_ids=invalid)


def test_fixed_provider_paths_base64_and_disable_previous_version():
    from unittest.mock import Mock
    from io import BytesIO

    service = ScalewaySecretManagerHTTP(
        region="fr-par", api_token=lambda: "fixture-valid-scw-token-" + ("x" * 32),
    )
    seen = []
    class Reply:
        status = 200
        def __init__(self, doc):
            self.fp = BytesIO(json.dumps(doc).encode())
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, count):
            return self.fp.read(count)
    class Opener:
        def open(self, request, timeout):
            seen.append((request.full_url, request.get_method(),
                         request.data, request.headers.get("X-auth-token")))
            if request.get_method() == "POST":
                return Reply({"secret_id": SECRET_ID, "revision": 2, "status": "enabled"})
            return Reply({"secret_id": SECRET_ID, "type": "opaque",
                          "data": base64.b64encode(b'{"fixture":true}').decode()})
    service.opener = Opener()
    assert service.access_latest(SECRET_ID) == b'{"fixture":true}'
    assert service.add_version(SECRET_ID, b'{"fixture":true}') == 2
    assert all(link.startswith(
        "https://api.scaleway.com/secret-manager/v1beta1/regions/fr-par/secrets/"
    ) for link, *_ in seen)
    assert seen[0][1] == "GET" and seen[1][1] == "POST"
    assert seen[0][3].startswith("fixture-valid-scw-token-")
    assert json.loads(seen[1][2])["disable_previous"] is True
    assert base64.b64decode(json.loads(seen[1][2])["data"]) == b'{"fixture":true}'


def test_invalid_provider_region_id_and_untrusted_method_are_rejected():
    with pytest.raises(ValueError, match="config"):
        ScalewaySecretManagerHTTP(region="us-east", api_token=lambda: "bad")
    service = ScalewaySecretManagerHTTP(region="fr-par", api_token=lambda: "bad")
    with pytest.raises(CalendarVerificationError, match="uuid"):
        service.access_latest("../../other-secrets")
    with pytest.raises(CalendarVerificationError, match="iam_credential"):
        service.access_latest(SECRET_ID)


def test_wrong_provider_secret_type_identity_or_base64_fail_closed():
    from io import BytesIO
    service = ScalewaySecretManagerHTTP(
        region="fr-par", api_token=lambda: "fixture-scw-token-" + ("z" * 36),
    )
    result = {"secret_id": SECRET_ID, "type": "opaque",
              "data": base64.b64encode(b"ok").decode()}
    class Reply:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def read(self, _: int):
            return json.dumps(result).encode()
    class Opener:
        def open(self, *_args, **_kwargs):
            return Reply()
    service.opener = Opener()
    assert service.access_latest(SECRET_ID) == b"ok"
    result["type"] = "key_value"
    with pytest.raises(CalendarVerificationError, match="opaque"):
        service.access_latest(SECRET_ID)
    result["type"] = "opaque"
    result["secret_id"] = str(uuid4())
    with pytest.raises(CalendarVerificationError, match="identity"):
        service.access_latest(SECRET_ID)
    result["secret_id"] = SECRET_ID
    result["data"] = "#invalid#"
    with pytest.raises(CalendarVerificationError, match="base64"):
        service.access_latest(SECRET_ID)



def test_provider_ack_without_persisted_secret_never_counts_as_connection():
    class LostWrite(FakeIAMGateway):
        def add_version(self, secret_id, payload):
            self.calls.append(("POST_ACK_BUT_LOST", secret_id))
            return 1

    remote = LostWrite()
    manager, remote = vault(remote)
    with pytest.raises(CalendarVerificationError, match="write_readback"):
        manager.put_verified_offline(credential(), at=NOW)
    with pytest.raises(CalendarVerificationError, match="missing_or_revoked"):
        manager.get_active(
            tenant_id=TENANT, calendar_id=CAL,
            provider_account_ref=ACCOUNT,
        )


def test_provider_ack_without_revocation_tombstone_does_not_claim_revoke():
    gateway = FakeIAMGateway()
    manager, _ = vault(gateway)
    manager.put_verified_offline(credential(), at=NOW)

    def ack_without_write(_secret_id, _payload):
        return 2
    gateway.add_version = ack_without_write
    with pytest.raises(CalendarVerificationError, match="revoke_readback"):
        manager.revoke_local(
            tenant_id=TENANT, calendar_id=CAL,
            provider_account_ref=ACCOUNT, at=NOW,
        )
    assert manager.get_active(
        tenant_id=TENANT, calendar_id=CAL,
        provider_account_ref=ACCOUNT,
    ).refresh_token == "fixture-refresh-secret"



def test_external_vault_refreshes_google_readonly_lease_without_local_secret_file(tmp_path):
    from empire_os.inbound_google_calendar_credentials import VaultBackedGoogleCalendarResolver
    from empire_os.inbound_google_calendar_adapter import ApprovedCalendarBinding

    manager, gateway = vault()
    manager.put_verified_offline(credential(), at=NOW)
    refresh_calls = []
    class ReadOnlyTokenExchange:
        def post_form(self, fields):
            refresh_calls.append(dict(fields))
            return {
                "token_type": "Bearer", "expires_in": 1800,
                "access_token": "fixture-google-rotated-access",
            }
    binding = ApprovedCalendarBinding(
        tenant_id=TENANT, calendar_id=CAL,
        provider_account_ref=ACCOUNT,
        owner_approved=True, account_access_verified=True,
    )
    with manager:
        resolver = VaultBackedGoogleCalendarResolver(
            vault=manager, token_endpoint=ReadOnlyTokenExchange(),
            client_secret_provider=lambda client_id: "fixture-google-client-secret",
            now_provider=lambda: NOW + timedelta(minutes=19),
        )
        lease, access_token = resolver.acquire(binding=binding)
        assert access_token == "fixture-google-rotated-access"
        assert lease.granted_scopes == SCOPES
        assert lease.calendar_id == CAL
        assert len(refresh_calls) == 1
        assert refresh_calls[0]["grant_type"] == "refresh_token"
        assert refresh_calls[0]["refresh_token"] == "fixture-refresh-secret"
        assert refresh_calls[0]["client_id"] == "fixture-google-client"
        assert manager.get_active(
            tenant_id=TENANT, calendar_id=CAL,
            provider_account_ref=ACCOUNT,
        ).access_token == "fixture-google-rotated-access"
    assert len([call for call in gateway.calls if call[0] == "POST"]) == 2
    assert not list(tmp_path.iterdir())


def test_external_vault_revocation_blocks_lease_before_google_refresh():
    from empire_os.inbound_google_calendar_credentials import VaultBackedGoogleCalendarResolver
    from empire_os.inbound_google_calendar_adapter import ApprovedCalendarBinding

    manager, gateway = vault()
    manager.put_verified_offline(credential(), at=NOW)
    manager.revoke_local(
        tenant_id=TENANT, calendar_id=CAL,
        provider_account_ref=ACCOUNT, at=NOW,
    )
    exchanges = []
    class NeverExchange:
        def post_form(self, data):
            exchanges.append(data)
            raise AssertionError("no refresh permitted for revoked calendar")
    resolver = VaultBackedGoogleCalendarResolver(
        vault=manager, token_endpoint=NeverExchange(),
        client_secret_provider=lambda _: "fixture-secret",
        now_provider=lambda: NOW + timedelta(minutes=19),
    )
    approved = ApprovedCalendarBinding(
        tenant_id=TENANT, calendar_id=CAL,
        provider_account_ref=ACCOUNT,
        owner_approved=True, account_access_verified=True,
    )
    with pytest.raises(CalendarVerificationError, match="missing_or_revoked"):
        resolver.acquire(binding=approved)
    assert exchanges == []
