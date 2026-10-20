"""Fail-closed server-only Google Calendar OAuth read capability boundary.

The authoritative OAuth client/vault is an independent integration. This
module NEVER creates or stores Google OAuth tokens and NEVER presents browser
auth endpoints. A production resolver must validate the actual Google-granted
scopes, session owner, refresh lifecycle and revocation *before* returning.

A fake resolver is suitable for deterministic tests, not an identity proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarFreeBusyStatus, CalendarReadTransport,
    CalendarStatusProof, CalendarVerificationError, TrackedCalendarAppointment,
    verify_google_booking_readback, verify_google_freebusy_readback,
)

EVENTS_READ = "https://www.googleapis.com/auth/calendar.events.readonly"
OWNED_EVENTS_READ = "https://www.googleapis.com/auth/calendar.events.owned.readonly"
CALENDAR_READ = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_FREEBUSY = "https://www.googleapis.com/auth/calendar.freebusy"
EVENTS_FREEBUSY = "https://www.googleapis.com/auth/calendar.events.freebusy"
ALLOWED_GOOGLE_READ_SCOPES = frozenset({
    EVENTS_READ, OWNED_EVENTS_READ, CALENDAR_READ, CALENDAR_FREEBUSY, EVENTS_FREEBUSY,
})
EVENT_SCOPES = frozenset({EVENTS_READ, OWNED_EVENTS_READ, CALENDAR_READ, EVENTS_FREEBUSY})
AVAILABILITY_SCOPES = frozenset({CALENDAR_READ, CALENDAR_FREEBUSY, EVENTS_FREEBUSY})


@dataclass(frozen=True)
class CalendarReadLease:
    tenant_id: str
    calendar_id: str
    provider_account_ref: str
    granted_scopes: frozenset[str]
    issued_at: datetime
    expires_at: datetime
    approved_by_customer: bool
    server_verified_grant: bool

    def check(
        self, *, binding: ApprovedCalendarBinding, now: datetime,
        need_events: bool = False, need_freebusy: bool = False,
    ) -> None:
        binding.check()
        if not isinstance(self.granted_scopes, frozenset):
            raise CalendarVerificationError("invalid_oauth_scope_claim_type")
        if not self.granted_scopes or not self.granted_scopes <= ALLOWED_GOOGLE_READ_SCOPES:
            raise CalendarVerificationError("calendar_write_or_unknown_scopes_denied")
        if self.tenant_id != binding.tenant_id or self.calendar_id != binding.calendar_id:
            raise CalendarVerificationError("calendar_oauth_cross_tenant_or_calendar")
        if self.provider_account_ref != binding.provider_account_ref:
            raise CalendarVerificationError("calendar_oauth_account_mismatch")
        if not self.approved_by_customer or not self.server_verified_grant:
            raise CalendarVerificationError("calendar_owner_grant_not_verified")
        if (now.tzinfo is None or now.utcoffset() is None or
            self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None or
            self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None):
            raise CalendarVerificationError("invalid_oauth_lease_timezone")
        if not self.issued_at <= now < self.expires_at:
            raise CalendarVerificationError("expired_or_future_calendar_lease")
        if self.expires_at - self.issued_at > timedelta(hours=1):
            raise CalendarVerificationError("calendar_access_lease_too_long")
        if need_events and not (self.granted_scopes & EVENT_SCOPES):
            raise CalendarVerificationError("calendar_event_read_scope_required")
        if need_freebusy and not (self.granted_scopes & AVAILABILITY_SCOPES):
            raise CalendarVerificationError("calendar_freebusy_scope_required")


class CalendarReadTokenResolver(Protocol):
    def acquire(
        self, *, binding: ApprovedCalendarBinding,
    ) -> tuple[CalendarReadLease, str]:
        """Access token must come from a tenant-scoped, revocable secret vault."""


def read_provisioned_google_appointment(
    *,
    binding: ApprovedCalendarBinding,
    link: TrackedCalendarAppointment,
    resolver: CalendarReadTokenResolver,
    transport: CalendarReadTransport,
    observed_at: datetime,
    previously_verified: CalendarStatusProof | None = None,
) -> CalendarStatusProof:
    """Authenticate scope and tenant before even calling Google events.get."""
    lease, token = resolver.acquire(binding=binding)
    lease.check(binding=binding, now=observed_at, need_events=True)
    return verify_google_booking_readback(
        binding=binding, link=link, transport=transport,
        token=token, observed_at=observed_at,
        previously_verified=previously_verified,
    )


def read_provisioned_google_occupancy(
    *,
    binding: ApprovedCalendarBinding,
    resolver: CalendarReadTokenResolver,
    transport: CalendarReadTransport,
    time_min: datetime,
    time_max: datetime,
    observed_at: datetime,
) -> CalendarFreeBusyStatus:
    """FreeBusy is occupancy, NEVER an authorisation to create an event."""
    lease, token = resolver.acquire(binding=binding)
    lease.check(binding=binding, now=observed_at, need_freebusy=True)
    return verify_google_freebusy_readback(
        binding=binding, time_min=time_min, time_max=time_max,
        token=token, transport=transport,
    )
