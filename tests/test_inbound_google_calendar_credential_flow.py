"""Complete consent -> vaulted read-only credential -> calendar proof fixture.

No real customer account, external Google request, calendar write, phone call
or financial transaction occurs in this integration regression.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet

from empire_os.inbound_booking_workflow import WorkflowPolicy
from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_calendar_oauth_onboarding import OfflineGoogleConsentStateStore
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_calendar_projection import project_calendar_evidence_offline
from empire_os.inbound_calendar_token_vault import OfflineCalendarCredentialVault
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, TrackedCalendarAppointment,
)
from empire_os.inbound_google_calendar_credentials import VaultBackedGoogleCalendarResolver
from empire_os.inbound_google_calendar_enrollment import enroll_google_calendar_offline
from empire_os.inbound_calendar_oauth_boundary import (
    CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ,
    read_provisioned_google_appointment,
)
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "pilot-company-test@example.org"
CLIENT = "pilot-oauth-client.apps.googleusercontent.com"
SCOPES = {EVENTS_READ, CALENDAR_FREEBUSY, CALENDAR_LIST_READ}


class GoogleTokenFixture:
    def __init__(self):
        self.operations = []

    def post_form(self, fields):
        self.operations.append(fields["grant_type"])
        if fields["grant_type"] == "refresh_token":
            return {
                "token_type": "Bearer", "expires_in": 1700,
                "access_token": "new-access-token-after-refresh",
            }
        return {
            "token_type": "Bearer", "expires_in": 1200,
            "scope": " ".join(sorted(SCOPES)),
            "access_token": "fresh-google-access-token",
            "refresh_token": "secret-google-refresh-token",
        }


class GoogleCalendarFixture:
    def __init__(self):
        self.operations = []

    def fetch(self, *, method, path, token, body=None):
        self.operations.append((method, path))
        assert method == "GET" and token == "fresh-google-access-token"
        if "/users/me/calendarList/" in path:
            return {"id": CAL, "accessRole": "owner"}
        return {
            "id": "confirmed-appointment-1",
            "status": "confirmed", "transparency": "opaque",
            "updated": "2026-10-20T12:00:00Z",
            "start": {"dateTime": "2026-10-21T10:00:00+01:00"},
            "end": {"dateTime": "2026-10-21T10:30:00+01:00"},
            "extendedProperties": {"private": {
                "empire_recovery_tenant": "pilot-tenant",
                "empire_recovery_call": "first-inbound-call",
                "empire_recovery_ref": "operator-reviewed-intent",
            }},
        }


def test_one_time_google_consent_to_verified_booking_projection(tmp_path):
    token_source = GoogleTokenFixture()
    provider = GoogleCalendarFixture()
    approved = ApprovedCalendarBinding(
        tenant_id="pilot-tenant", calendar_id=CAL,
        provider_account_ref="private-google-owner-ref",
        owner_approved=True, account_access_verified=True,
    )
    with OfflineGoogleConsentStateStore(
        tmp_path / "consent.db", encryption_key=Fernet.generate_key(),
    ) as consent, OfflineCalendarCredentialVault(
        tmp_path / "vault.db", active_key=Fernet.generate_key(),
    ) as vault, OfflineCalendarRegistry(
        tmp_path / "registry.db",
    ) as registry, OfflineRecoveryStore(
        tmp_path / "recovery.db",
    ) as recovery, OfflineBookingWorkflowStore(
        tmp_path / "workflow.db",
    ) as workflow:
        start = consent.begin(
            tenant_id="pilot-tenant", admin_subject="authenticated-owner",
            client_id=CLIENT, redirect_uri="https://example.org/oauth/callback",
            now=NOW, selected_calendar_id=CAL,
        )
        state = parse_qs(urlsplit(start.authorization_url).query)["state"][0]
        ticket = consent.consume(
            tenant_id="pilot-tenant", admin_subject="authenticated-owner",
            state=state, authorization_code="local-fixture-only-code",
            now=NOW + timedelta(seconds=10),
        )
        connected = enroll_google_calendar_offline(
            ticket=ticket, binding=approved, expected_client_id=CLIENT,
            client_secret="client-secret-not-in-repo",
            owner_approval_evidence_ref="operator-approved-owner-attestation",
            endpoint=token_source, google_read_transport=provider,
            registry=registry, vault=vault, now=NOW + timedelta(seconds=10),
        )
        assert connected.calendar_binding_created and not connected.live_bookings_created
        contact = pseudonymise_inbound_contact(
            "+442071234567", tenant_id="pilot-tenant",
            signing_key="pilot-private-contact-hmac-key-32bytes",
        )
        registry.register_appointment_offline(TrackedCalendarAppointment(
            tenant_id="pilot-tenant", calendar_id=CAL,
            event_id="confirmed-appointment-1", call_id="first-inbound-call",
            contact_key=contact, tracked_ref="operator-reviewed-intent",
        ))
        resolver = VaultBackedGoogleCalendarResolver(
            vault=vault, token_endpoint=token_source,
            client_secret_provider=lambda client: "server-only-client-secret",
            now_provider=lambda: NOW + timedelta(minutes=2),
        )
        lease, token = resolver.acquire(binding=approved)
        assert lease.granted_scopes == frozenset(SCOPES)
        previous = registry.current_proof(
            calendar_id=CAL, event_id="confirmed-appointment-1",
        )
        proof = read_provisioned_google_appointment(
            binding=approved,
            link=registry.get_link(calendar_id=CAL, event_id="confirmed-appointment-1"),
            resolver=resolver, transport=provider,
            observed_at=NOW + timedelta(minutes=2),
            previously_verified=previous,
        )
        assert proof.status == "confirmed"
        # Persist the provider proof to an independently tracked outbox.
        stored, created = registry.verified_readback_offline(
            tenant_id="pilot-tenant", calendar_id=CAL, event_id="confirmed-appointment-1",
            token=token, transport=provider, observed_at=NOW + timedelta(minutes=2),
        )
        assert created and stored.canonical_ref == proof.canonical_ref
        recovery.append_offline(RecoveryEvent(
            tenant_id="pilot-tenant", event_id="provider-missed-1",
            call_id="first-inbound-call",
            occurred_at=(NOW - timedelta(minutes=10)).isoformat(),
            kind="unanswered", origin="provider", verified=True, synthetic=False,
        ))
        delivery = project_calendar_evidence_offline(
            registry=registry, recovery=recovery, workflow=workflow,
            tenant_id="pilot-tenant", as_of=NOW + timedelta(minutes=3),
        )
        assert delivery.acknowledged == 1
        assert recovery.report("pilot-tenant")["confirmed_bookings"] == 1
        assert recovery.report("pilot-tenant")["verified_paid_recovery_minor_by_currency"] == {}
        assert workflow.summary(
            WorkflowPolicy("pilot-tenant"), as_of=NOW + timedelta(minutes=3),
        )["active_calendar_confirmations"] == 1
        assert registry.projection_counts("pilot-tenant") == {
            "pending": 0, "complete": 1,
        }
        assert token_source.operations == ["authorization_code"]
        assert all(method == "GET" for method, _ in provider.operations)
        assert b"secret-google-refresh-token" not in (tmp_path / "registry.db").read_bytes()
        assert b"secret-google-refresh-token" not in (tmp_path / "vault.db").read_bytes()
