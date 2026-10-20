"""Customer calendar access verification and revocable vault-backed resolver.

Separate from the application router: instantiation requires an explicitly
authorised secret vault + OAuth exchange endpoint, both server controlled.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import quote

from empire_os.inbound_calendar_oauth_boundary import (
    CALENDAR_LIST_READ, CalendarReadLease,
)
from empire_os.inbound_calendar_token_vault import (
    CalendarCredential, OfflineCalendarCredentialVault,
)
from empire_os.inbound_scaleway_calendar_vault import ScalewaySecretManagerCalendarVault
from empire_os.inbound_google_oauth_exchange import (
    OAuthTokenEndpoint, refresh_google_calendar_access,
)
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarReadTransport, CalendarVerificationError,
)


@dataclass(frozen=True)
class VerifiedCalendarAccess:
    tenant_id: str
    calendar_id: str
    provider_account_ref: str
    google_access_role: str
    provider_calendar_read_verified: bool = True
    calendar_write_authorized: bool = False


def verify_google_calendar_access_role(
    *,
    binding: ApprovedCalendarBinding,
    token: str,
    granted_scopes: frozenset[str],
    transport: CalendarReadTransport,
) -> VerifiedCalendarAccess:
    """Google's calendarList.get must confirm exact selected calendar access.

    The customer's explicit consent and authenticated tenant identity remain
    a separate prerequisite; being a 'writer' or 'owner' is not permission to
    programmatically create bookings with this read-only token.
    """
    binding.check()
    if CALENDAR_LIST_READ not in granted_scopes and (
        "https://www.googleapis.com/auth/calendar.readonly" not in granted_scopes
    ):
        raise CalendarVerificationError("google_calendar_list_read_scope_required")
    if not isinstance(token, str) or not token.strip():
        raise CalendarVerificationError("google_calendar_access_token_required")
    path = "/calendar/v3/users/me/calendarList/" + quote(binding.calendar_id, safe="")
    raw = transport.fetch(method="GET", path=path, token=token)
    if not isinstance(raw, dict) or raw.get("id") != binding.calendar_id:
        raise CalendarVerificationError("google_selected_calendar_identity_mismatch")
    role = raw.get("accessRole")
    if role not in {"owner", "writer"} or raw.get("deleted") is True:
        raise CalendarVerificationError("google_selected_calendar_private_access_denied")
    return VerifiedCalendarAccess(
        tenant_id=binding.tenant_id, calendar_id=binding.calendar_id,
        provider_account_ref=binding.provider_account_ref, google_access_role=role,
    )


class VaultBackedGoogleCalendarResolver:
    """Refresh a customer-approved lease, never expose secrets to public API."""

    def __init__(
        self, *, vault: OfflineCalendarCredentialVault | ScalewaySecretManagerCalendarVault,
        token_endpoint: OAuthTokenEndpoint,
        client_secret_provider: Callable[[str], str],
        now_provider: Callable[[], datetime] | None = None,
    ):
        if not isinstance(vault, (OfflineCalendarCredentialVault, ScalewaySecretManagerCalendarVault)):
            raise ValueError("verified_calendar_vault_backend_required")
        if not callable(getattr(token_endpoint, "post_form", None)) or not callable(client_secret_provider):
            raise ValueError("trusted_google_token_exchange_required")
        self.vault = vault
        self.endpoint = token_endpoint
        self.client_secret_provider = client_secret_provider
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def acquire(self, *, binding: ApprovedCalendarBinding) -> tuple[CalendarReadLease, str]:
        binding.check()
        now = self.now_provider()
        current = self.vault.get_active(
            tenant_id=binding.tenant_id,
            calendar_id=binding.calendar_id,
            provider_account_ref=binding.provider_account_ref,
        )
        # Short margin leaves enough lifetime for bounded Google request.
        if current.expires_at <= now + timedelta(minutes=2):
            new = refresh_google_calendar_access(
                client_id=current.google_client_id,
                client_secret=self.client_secret_provider(current.google_client_id),
                refresh_token=current.refresh_token,
                prior_scopes=current.scopes,
                endpoint=self.endpoint,
                now=now,
            )
            updated = CalendarCredential(
                tenant_id=current.tenant_id, calendar_id=current.calendar_id,
                provider_account_ref=current.provider_account_ref,
                google_client_id=current.google_client_id,
                access_token=new.access_token,
                refresh_token=new.refresh_token or current.refresh_token,
                scopes=new.granted_scopes,
                issued_at=new.issued_at, expires_at=new.expires_at,
                customer_approved=current.customer_approved,
                provider_grant_verified=current.provider_grant_verified,
            )
            self.vault.put_verified_offline(updated, at=now)
            current = updated
        lease = CalendarReadLease(
            tenant_id=current.tenant_id, calendar_id=current.calendar_id,
            provider_account_ref=current.provider_account_ref,
            granted_scopes=current.scopes,
            issued_at=current.issued_at,
            expires_at=current.expires_at,
            approved_by_customer=current.customer_approved,
            server_verified_grant=current.provider_grant_verified,
        )
        lease.check(binding=binding, now=now)
        return lease, current.access_token
