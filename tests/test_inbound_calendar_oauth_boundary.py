"""Calendar OAuth read boundaries; no credentials or provider calls in tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.inbound_calendar_oauth_boundary import (
    ALLOWED_GOOGLE_READ_SCOPES, CALENDAR_FREEBUSY, CALENDAR_READ,
    EVENTS_READ, CalendarReadLease,
    read_provisioned_google_appointment, read_provisioned_google_occupancy,
)
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarVerificationError, TrackedCalendarAppointment,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "approved-calendar@example.org"


def binding():
    return ApprovedCalendarBinding(
        tenant_id="tenant-one", calendar_id=CAL,
        provider_account_ref="private-oauth-account-ref",
        owner_approved=True, account_access_verified=True,
    )


def link():
    return TrackedCalendarAppointment(
        tenant_id="tenant-one", calendar_id=CAL,
        event_id="trusted-event-1", call_id="call-1",
        contact_key="a" * 64, tracked_ref="booking-intent-1",
    )


def lease(scopes=None):
    return CalendarReadLease(
        tenant_id="tenant-one", calendar_id=CAL,
        provider_account_ref="private-oauth-account-ref",
        granted_scopes=frozenset(scopes or {CALENDAR_READ}),
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=35),
        approved_by_customer=True, server_verified_grant=True,
    )


class Vault:
    def __init__(self, grant):
        self.grant = grant
        self.calls = 0

    def acquire(self, *, binding):
        self.calls += 1
        assert binding.calendar_id == CAL
        return self.grant, "opaque-test-token-should-never-persist"


class Transport:
    def __init__(self):
        self.calls = []

    def fetch(self, *, method, path, token, body=None):
        assert token == "opaque-test-token-should-never-persist"
        self.calls.append((method, path, body))
        if method == "POST":
            return {"kind": "calendar#freeBusy",
                    "calendars": {CAL: {"busy": []}}}
        return {
            "id": "trusted-event-1", "status": "confirmed",
            "updated": "2026-10-20T11:58:00Z",
            "transparency": "opaque",
            "start": {"dateTime": "2026-10-21T14:00:00+01:00"},
            "end": {"dateTime": "2026-10-21T14:30:00+01:00"},
            "extendedProperties": {"private": {
                "empire_recovery_tenant": "tenant-one",
                "empire_recovery_call": "call-1",
                "empire_recovery_ref": "booking-intent-1",
            }},
        }


def test_readonly_lease_reaches_provider_and_never_mints_booking():
    transport = Transport()
    p = read_provisioned_google_appointment(
        binding=binding(), link=link(),
        resolver=Vault(lease()), transport=transport, observed_at=NOW,
    )
    assert p.status == "confirmed" and p.live_booking_writes is False
    assert len(transport.calls) == 1
    assert transport.calls[0][0] == "GET"


def test_separately_scoped_freebusy_still_not_bookable():
    t = Transport()
    result = read_provisioned_google_occupancy(
        binding=binding(), resolver=Vault(lease({CALENDAR_FREEBUSY})),
        transport=t, time_min=NOW,
        time_max=NOW + timedelta(minutes=30), observed_at=NOW,
    )
    assert result.calendar_busy is False
    assert result.booking_confirmed is False
    assert result.available_slot_confirmed is False
    assert t.calls[0][0] == "POST"


@pytest.mark.parametrize("bad", [
    {"https://www.googleapis.com/auth/calendar"},
    {"https://www.googleapis.com/auth/calendar.events"},
    {"https://www.googleapis.com/auth/calendar", CALENDAR_READ},
    {"https://www.googleapis.com/auth/calendar.acls"},
    set(),
])
def test_write_or_unknown_scopes_cannot_reach_provider(bad):
    t = Transport()
    # Empty set must remain empty, not default to readonly.
    denied = replace(lease(), granted_scopes=frozenset(bad))
    with pytest.raises(CalendarVerificationError, match="scopes_denied"):
        read_provisioned_google_appointment(
            binding=binding(), link=link(), resolver=Vault(denied),
            transport=t, observed_at=NOW,
        )
    assert t.calls == []


def test_only_freebusy_scope_cannot_fetch_private_event():
    t = Transport()
    with pytest.raises(CalendarVerificationError, match="event_read_scope"):
        read_provisioned_google_appointment(
            binding=binding(), link=link(),
            resolver=Vault(lease({CALENDAR_FREEBUSY})),
            transport=t, observed_at=NOW,
        )
    assert t.calls == []


def test_event_scope_does_not_grant_freebusy_without_extra_scope():
    t = Transport()
    with pytest.raises(CalendarVerificationError, match="freebusy_scope"):
        read_provisioned_google_occupancy(
            binding=binding(), resolver=Vault(lease({EVENTS_READ})),
            transport=t, time_min=NOW,
            time_max=NOW + timedelta(minutes=30), observed_at=NOW,
        )
    assert t.calls == []


@pytest.mark.parametrize("change,reason", [
    ({"tenant_id": "different"}, "cross_tenant"),
    ({"calendar_id": "other@example.org"}, "cross_tenant"),
    ({"provider_account_ref": "other-user"}, "account_mismatch"),
    ({"approved_by_customer": False}, "owner_grant_not_verified"),
    ({"server_verified_grant": False}, "owner_grant_not_verified"),
    ({"expires_at": NOW - timedelta(seconds=1)}, "expired_or_future"),
    ({"issued_at": NOW + timedelta(seconds=1)}, "expired_or_future"),
    ({"expires_at": NOW + timedelta(hours=3)}, "lease_too_long"),
])
def test_bad_oauth_owner_or_expired_token_is_rejected_before_request(change, reason):
    t = Transport()
    with pytest.raises(CalendarVerificationError, match=reason):
        read_provisioned_google_appointment(
            binding=binding(), link=link(), resolver=Vault(replace(lease(), **change)),
            transport=t, observed_at=NOW,
        )
    assert t.calls == []


def test_none_of_the_grant_records_contain_secrets():
    assert "opaque-test-token" not in str(lease())
    assert all("readonly" in s or "freebusy" in s for s in ALLOWED_GOOGLE_READ_SCOPES)
