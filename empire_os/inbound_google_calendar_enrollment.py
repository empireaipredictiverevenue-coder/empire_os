"""Operator-authorised calendar enrollment, from one-time OAuth ticket to vault.

No HTTP callback route is exposed, and no Google account is accessed unless a
privileged integration explicitly invokes this function after tenant-owner
identity checks. Tokens are never written to the calendar registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from empire_os.inbound_calendar_oauth_onboarding import OneTimeGoogleCodeTicket
from empire_os.inbound_calendar_token_vault import (
    CalendarCredential, OfflineCalendarCredentialVault,
)
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_google_calendar_credentials import (
    verify_google_calendar_access_role,
)
from empire_os.inbound_google_oauth_exchange import (
    OAuthTokenEndpoint, exchange_google_pkce_code,
)
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarReadTransport, CalendarVerificationError,
)


@dataclass(frozen=True)
class GoogleCalendarEnrollmentResult:
    tenant_id: str
    calendar_id: str
    provider_account_ref: str
    credential_vault_write: bool
    calendar_binding_created: bool
    status: str = "onboarded_to_offline_secret_vault_only"
    live_bookings_created: bool = False
    customer_messages_sent: bool = False


def enroll_google_calendar_offline(
    *,
    ticket: OneTimeGoogleCodeTicket,
    binding: ApprovedCalendarBinding,
    expected_client_id: str,
    client_secret: str,
    owner_approval_evidence_ref: str,
    endpoint: OAuthTokenEndpoint,
    google_read_transport: CalendarReadTransport,
    vault: OfflineCalendarCredentialVault,
    registry: OfflineCalendarRegistry,
    now: datetime,
) -> GoogleCalendarEnrollmentResult:
    """Explicit privileged call only: validate BEFORE retaining credential.

    Google list access role provides evidence of access to this calendar, not
    proof that the OAuth user is the correct EmpireOS tenant administrator.
    That must be established by the existing authenticated user session.
    """
    if not isinstance(ticket, OneTimeGoogleCodeTicket):
        raise CalendarVerificationError("consumed_one_time_oauth_ticket_required")
    binding.check()
    if (not isinstance(owner_approval_evidence_ref, str) or
        not owner_approval_evidence_ref.strip() or
        ticket.tenant_id != binding.tenant_id):
        raise CalendarVerificationError("customer_approval_or_tenant_mismatch")
    if registry.read_only:
        raise CalendarVerificationError("calendar_enrollment_requires_private_writable_registry")
    existing = registry.get_binding(binding.calendar_id)
    if existing is not None and existing != binding:
        raise CalendarVerificationError("already_owned_calendar_binding_mismatch")

    grant = exchange_google_pkce_code(
        ticket, expected_client_id=expected_client_id,
        client_secret=client_secret, endpoint=endpoint, now=now,
    )
    verification = verify_google_calendar_access_role(
        binding=binding, token=grant.access_token,
        granted_scopes=grant.granted_scopes,
        transport=google_read_transport,
    )
    if verification.tenant_id != ticket.tenant_id or not verification.provider_calendar_read_verified:
        raise CalendarVerificationError("oauth_calendar_verification_failed")

    credential = CalendarCredential(
        tenant_id=binding.tenant_id, calendar_id=binding.calendar_id,
        provider_account_ref=binding.provider_account_ref,
        google_client_id=ticket.client_id,
        access_token=grant.access_token,
        refresh_token=grant.refresh_token,
        scopes=grant.granted_scopes,
        issued_at=grant.issued_at, expires_at=grant.expires_at,
        customer_approved=True, provider_grant_verified=True,
    )
    # Store secrets in encrypted isolated store first; if the registry binding
    # fails, immediately block local access and require a fresh customer grant.
    # This is NOT a transaction across stores nor a Google token revocation.
    vault.put_verified_offline(credential, at=now)
    try:
        created = registry.register_binding_offline(
            binding, approval_ref=owner_approval_evidence_ref,
        )
    except Exception:
        vault.revoke_local(
            tenant_id=binding.tenant_id,
            calendar_id=binding.calendar_id,
            provider_account_ref=binding.provider_account_ref,
            at=now,
        )
        raise
    return GoogleCalendarEnrollmentResult(
        tenant_id=binding.tenant_id,
        calendar_id=binding.calendar_id,
        provider_account_ref=binding.provider_account_ref,
        credential_vault_write=True,
        calendar_binding_created=created,
    )
