"""Explicit, operator-configured OAuth completion adapter for customer calendars.

Uses existing Google exchange, read-only role verification, encrypted staging
vault and approved registry. This is NOT installed in the dark staging service.
No live token, key, calendar or internet access is created by importing it.
Production activation still requires a reviewed KMS-backed credential backend.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import hmac

from empire_os.inbound_calendar_connection_identity import CalendarConnectionPrincipal
from empire_os.inbound_calendar_oauth_onboarding import OneTimeGoogleCodeTicket
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_calendar_token_vault import OfflineCalendarCredentialVault
from empire_os.inbound_scaleway_calendar_vault import ScalewaySecretManagerCalendarVault
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarReadTransport, CalendarVerificationError,
)
from empire_os.inbound_google_calendar_enrollment import (
    GoogleCalendarEnrollmentResult, enroll_google_calendar_offline,
)
from empire_os.inbound_google_oauth_exchange import OAuthTokenEndpoint


class ApprovedGoogleCalendarCompletion:
    """A fresh backend permission check is required at every invocation.

    account_binding is an operator-controlled trusted map, not the request's
    calendar ID plus self-attested ownership. The internal account reference
    is a tracking identifier, NOT proof of Google's user's true identity.
    """

    def __init__(
        self, *,
        expected_client_id: str,
        expected_redirect_uri: str,
        client_secret_provider: Callable[[], str],
        account_binding: Callable[[str, str, str], str | None],
        token_endpoint: OAuthTokenEndpoint,
        calendar_transport: CalendarReadTransport,
        open_vault: Callable[[], OfflineCalendarCredentialVault | ScalewaySecretManagerCalendarVault],
        open_registry: Callable[[], OfflineCalendarRegistry],
        owner_membership_check: Callable[[str, str], bool],
        evidence_key: bytes,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if (not isinstance(expected_client_id, str) or not expected_client_id.strip()
            or not isinstance(expected_redirect_uri, str)
            or not expected_redirect_uri.startswith("https://")
            or not callable(client_secret_provider)
            or not callable(account_binding)
            or not callable(owner_membership_check)
            or not callable(getattr(token_endpoint, "post_form", None))
            or not callable(getattr(calendar_transport, "fetch", None))
            or not callable(open_vault)
            or not callable(open_registry)
            or not isinstance(evidence_key, bytes)
            or len(evidence_key) < 32):
            raise ValueError("approved_calendar_backend_dependencies_required")
        self.client_id = expected_client_id
        self.redirect_uri = expected_redirect_uri
        self.client_secret_provider = client_secret_provider
        self.account_binding = account_binding
        self.token_endpoint = token_endpoint
        self.calendar_transport = calendar_transport
        self.open_vault = open_vault
        self.open_registry = open_registry
        self.owner_membership_check = owner_membership_check
        self.evidence_key = evidence_key
        self.now = now or (lambda: datetime.now(timezone.utc))

    def __call__(
        self, ticket: OneTimeGoogleCodeTicket,
        principal: CalendarConnectionPrincipal,
    ) -> GoogleCalendarEnrollmentResult:
        if (not isinstance(ticket, OneTimeGoogleCodeTicket)
            or not isinstance(principal, CalendarConnectionPrincipal)
            or not isinstance(ticket.selected_calendar_id, str)
            or not ticket.selected_calendar_id.strip()
            or ticket.tenant_id != principal.tenant_id
            or ticket.admin_subject != principal.subject
            or ticket.client_id != self.client_id
            or ticket.redirect_uri != self.redirect_uri
            or principal.role not in {"owner", "admin"}):
            raise CalendarVerificationError("calendar_verified_owner_ticket_required")

        # A previously issued callback session is not sufficient when the
        # canonical account or membership has been revoked in the meantime.
        try:
            active = self.owner_membership_check(principal.subject, principal.tenant_id)
        except Exception:
            active = False
        if active is not True:
            raise CalendarVerificationError("calendar_owner_membership_no_longer_active")

        # The operator approval MUST already exist for the exact tenant,
        # owner and selected calendar. Never trust a provider ref in request.
        account_ref = self.account_binding(
            principal.tenant_id, principal.subject, ticket.selected_calendar_id,
        )
        if not isinstance(account_ref, str) or not account_ref.strip() or len(account_ref) > 240:
            raise CalendarVerificationError("calendar_operator_binding_required")
        approval_context = (
            principal.tenant_id + "\x00" + principal.subject + "\x00" +
            principal.token_id + "\x00" + ticket.selected_calendar_id +
            "\x00" + account_ref
        ).encode("utf-8")
        reference = "calendar-consent-owner-session:" + hmac.new(
            self.evidence_key, approval_context, sha256,
        ).hexdigest()

        binding = ApprovedCalendarBinding(
            tenant_id=principal.tenant_id,
            calendar_id=ticket.selected_calendar_id,
            provider_account_ref=account_ref,
            owner_approved=True,
            # This flag requests a check, not proof by itself: the trusted
            # enrollment function immediately calls Google's calendarList.
            account_access_verified=True,
        )
        secret = self.client_secret_provider()
        if not isinstance(secret, str) or not secret.strip():
            raise CalendarVerificationError("private_google_client_secret_required")
        # Fresh connections are mandatory: FastAPI sync callbacks run in
        # worker threads; a pooled SQLite connection is unsafe across threads.
        with self.open_vault() as vault, self.open_registry() as registry:
            if (not isinstance(vault, (OfflineCalendarCredentialVault, ScalewaySecretManagerCalendarVault))
                or not isinstance(registry, OfflineCalendarRegistry)
                or registry.read_only):
                raise CalendarVerificationError("trusted_calendar_storage_factories_required")
            result = enroll_google_calendar_offline(
                ticket=ticket,
                binding=binding,
                expected_client_id=self.client_id,
                client_secret=secret,
                owner_approval_evidence_ref=reference,
                endpoint=self.token_endpoint,
                google_read_transport=self.calendar_transport,
                vault=vault,
                registry=registry,
                now=self.now(),
            )
        if (result.tenant_id != principal.tenant_id
            or result.calendar_id != ticket.selected_calendar_id
            or result.provider_account_ref != account_ref
            or not result.credential_vault_write):
            raise CalendarVerificationError("calendar_enrollment_receipt_mismatch")
        return result
