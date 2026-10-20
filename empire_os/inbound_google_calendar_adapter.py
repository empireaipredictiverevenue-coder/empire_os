"""Explicitly read-only Google Calendar adapter for inbound revenue evidence.

The HTTP transport is optional and never constructed by an inbound API route.
The business/calendar binding and appointment link must be provisioned by
trusted backend code, never supplied as a self-attested webhook/client flag.

Google Calendar is the source of status only; an event is attributed to an
inbound call only with a matching calendar-private Empire marker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from empire_os.inbound_booking_workflow import InboundWorkflowEvent
from empire_os.inbound_revenue_recovery import RecoveryEvent


class CalendarVerificationError(ValueError):
    """Missing or untrusted calendar evidence; never confirm a booking."""


def _aware(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError) as exc:
        raise CalendarVerificationError("invalid_calendar_timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise CalendarVerificationError("calendar_timezone_required")
    return dt


@dataclass(frozen=True)
class ApprovedCalendarBinding:
    tenant_id: str
    calendar_id: str
    provider_account_ref: str
    owner_approved: bool = False
    account_access_verified: bool = False

    def __post_init__(self) -> None:
        for item in ("tenant_id", "calendar_id", "provider_account_ref"):
            value = getattr(self, item)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise CalendarVerificationError("invalid_calendar_binding")
        if not isinstance(self.owner_approved, bool) or not isinstance(self.account_access_verified, bool):
            raise CalendarVerificationError("invalid_calendar_approval_flags")

    def check(self) -> None:
        if not (self.owner_approved and self.account_access_verified):
            raise CalendarVerificationError("calendar_not_owner_approved_and_connected")


@dataclass(frozen=True)
class TrackedCalendarAppointment:
    tenant_id: str
    calendar_id: str
    event_id: str
    call_id: str
    contact_key: str
    tracked_ref: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "calendar_id", "event_id", "call_id", "tracked_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise CalendarVerificationError("invalid_appointment_link")
        if len(self.contact_key) != 64 or any(c not in "0123456789abcdef" for c in self.contact_key):
            raise CalendarVerificationError("invalid_appointment_contact_identity")


class CalendarReadTransport(Protocol):
    def fetch(self, *, method: str, path: str, token: str, body: dict | None = None) -> dict: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class GoogleCalendarReadOnlyHTTP:
    """Optional actual provider transport, with strict method/path allowlist.

    Caller must supply a valid OAuth access token obtained by a properly scoped
    identity and account lifecycle. No refresh or credentials are stored here.
    """

    def __init__(self, *, timeout_seconds: float = 8, max_response_bytes: int = 65536):
        if not 1 <= timeout_seconds <= 15 or not 1024 <= max_response_bytes <= 262144:
            raise ValueError("invalid_calendar_transport_bounds")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._opener = build_opener(_NoRedirect)

    def fetch(self, *, method: str, path: str, token: str, body: dict | None = None) -> dict:
        if not isinstance(token, str) or not token.strip() or len(token) > 8192:
            raise CalendarVerificationError("calendar_oauth_token_required")
        allowed = (
            method == "GET" and path.startswith("/calendar/v3/calendars/")
            and "/events/" in path and body is None
        ) or (
            method == "POST" and path == "/calendar/v3/freeBusy" and isinstance(body, dict)
        )
        if not allowed or "?" in path or "#" in path or "\\" in path or "//" in path:
            raise CalendarVerificationError("calendar_transport_method_denied")
        url = "https://www.googleapis.com" + path
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, method=method, data=payload, headers=headers)
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise CalendarVerificationError("calendar_read_not_confirmed")
                data = response.read(self.max_response_bytes + 1)
                if len(data) > self.max_response_bytes:
                    raise CalendarVerificationError("calendar_response_too_large")
                result = json.loads(data)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise CalendarVerificationError("calendar_provider_unavailable_or_invalid") from exc
        if not isinstance(result, dict):
            raise CalendarVerificationError("calendar_object_required")
        return result


@dataclass(frozen=True)
class CalendarStatusProof:
    tenant_id: str
    call_id: str
    calendar_id: str
    appointment_id: str
    canonical_ref: str
    status: str
    provider_updated_at: str | None
    observed_at: str
    starts_at: str
    ends_at: str
    provider: str = "google_calendar"
    live_booking_writes: bool = False
    customer_contact_authorized: bool = False


def verify_google_booking_readback(
    *,
    binding: ApprovedCalendarBinding,
    link: TrackedCalendarAppointment,
    token: str,
    transport: CalendarReadTransport,
    observed_at: datetime,
    previously_verified: CalendarStatusProof | None = None,
) -> CalendarStatusProof:
    """Read authenticated event.get; never treat event status alone as ownership."""
    binding.check()
    if (link.tenant_id != binding.tenant_id or
        link.calendar_id != binding.calendar_id):
        raise CalendarVerificationError("cross_tenant_or_calendar_booking_link")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise CalendarVerificationError("calendar_observation_time_requires_timezone")
    path = (
        "/calendar/v3/calendars/" + quote(binding.calendar_id, safe="") +
        "/events/" + quote(link.event_id, safe="")
    )
    raw = transport.fetch(method="GET", path=path, token=token)
    if not isinstance(raw, dict) or raw.get("id") != link.event_id:
        raise CalendarVerificationError("provider_appointment_id_mismatch")
    status = raw.get("status")
    if status not in {"confirmed", "cancelled"}:
        raise CalendarVerificationError("calendar_status_not_verified")

    canonical_ref = "gcal:" + sha256(
        (binding.calendar_id + "\x00" + link.event_id).encode("utf-8")
    ).hexdigest()
    priv = (raw.get("extendedProperties") or {}).get("private", {})
    match = (
        isinstance(priv, dict)
        and priv.get("empire_recovery_tenant") == link.tenant_id
        and priv.get("empire_recovery_call") == link.call_id
        and priv.get("empire_recovery_ref") == link.tracked_ref
    )
    # Cancelled exceptions can contain only an ID. Only an already confirmed
    # event with identical provenance allows such a sparse cancellation.
    if status == "cancelled" and not match:
        if previously_verified is None or (
            previously_verified.status not in {"confirmed", "cancelled"}
            or previously_verified.tenant_id != link.tenant_id
            or previously_verified.call_id != link.call_id
            or previously_verified.calendar_id != binding.calendar_id
            or previously_verified.appointment_id != link.event_id
            or previously_verified.canonical_ref != canonical_ref
        ):
            raise CalendarVerificationError("calendar_cancel_not_linked_to_verified_booking")
    elif not match:
        raise CalendarVerificationError("calendar_private_call_provenance_missing")

    prior = previously_verified
    if status == "cancelled" and prior is not None:
        starts, ends = prior.starts_at, prior.ends_at
    else:
        start_node = raw.get("start")
        end_node = raw.get("end")
        if not isinstance(start_node, dict) or not isinstance(end_node, dict):
            raise CalendarVerificationError("calendar_start_end_required")
        start_value = start_node.get("dateTime")
        end_value = end_node.get("dateTime")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            raise CalendarVerificationError("all_day_calendar_events_not_bookings")
        starts, ends = start_value, end_value
    start, end = _aware(starts), _aware(ends)
    if end <= start or end - start > timedelta(hours=24):
        raise CalendarVerificationError("invalid_provider_booking_window")
    if status == "confirmed" and raw.get("transparency", "opaque") != "opaque":
        raise CalendarVerificationError("transparent_event_not_confirmed_busy_booking")
    updated = raw.get("updated")
    if status == "confirmed" and not isinstance(updated, str):
        raise CalendarVerificationError("confirmed_booking_provider_revision_required")
    if updated is not None:
        if not isinstance(updated, str):
            raise CalendarVerificationError("provider_updated_time_invalid")
        updated_at = _aware(updated)
        if updated_at > observed_at + timedelta(minutes=5):
            raise CalendarVerificationError("provider_updated_time_in_future")
        if prior is not None and prior.provider_updated_at is not None:
            if updated_at < _aware(prior.provider_updated_at):
                raise CalendarVerificationError("stale_calendar_provider_revision")
        # A confirmation replay from before a sparse cancellation must never
        # resurrect a booking without a fresh provider revision.
        if prior is not None and prior.status == "cancelled" and status == "confirmed":
            if updated_at < _aware(prior.observed_at):
                raise CalendarVerificationError("stale_reconfirmation_after_cancellation")
    return CalendarStatusProof(
        tenant_id=link.tenant_id, call_id=link.call_id,
        calendar_id=binding.calendar_id, appointment_id=link.event_id,
        canonical_ref=canonical_ref, status=status,
        provider_updated_at=updated if isinstance(updated, str) else None,
        observed_at=observed_at.isoformat(),
        starts_at=starts, ends_at=ends,
    )


def calendar_proof_to_recovery_event(
    proof: CalendarStatusProof,
) -> RecoveryEvent:
    """Recorded readback time; no provider-created financial claims."""
    kind = "booking_confirmed" if proof.status == "confirmed" else "booking_cancelled"
    digest = sha256((
        proof.tenant_id + "\x00" + proof.canonical_ref + "\x00" +
        proof.status + "\x00" + (proof.provider_updated_at or proof.observed_at)
    ).encode()).hexdigest()
    return RecoveryEvent(
        tenant_id=proof.tenant_id,
        event_id="gcal-" + digest,
        call_id=proof.call_id,
        occurred_at=proof.provider_updated_at or proof.observed_at,
        kind=kind, origin="calendar",
        evidence_ref=proof.canonical_ref, verified=True, synthetic=False,
    )


def calendar_proof_to_workflow_event(
    proof: CalendarStatusProof,
    *, contact_key: str,
) -> InboundWorkflowEvent:
    recovery = calendar_proof_to_recovery_event(proof)
    return InboundWorkflowEvent(
        tenant_id=proof.tenant_id, event_id=recovery.event_id,
        call_id=proof.call_id, contact_key=contact_key,
        kind=("calendar_booking_confirmed" if proof.status == "confirmed"
              else "calendar_booking_cancelled"),
        occurred_at=recovery.occurred_at, origin="calendar_adapter",
        evidence_ref=proof.canonical_ref, verified=True, synthetic=False,
        appointment_id=proof.appointment_id, calendar_ref=proof.calendar_id,
        appointment_starts_at=proof.starts_at,
        appointment_ends_at=proof.ends_at,
    )


@dataclass(frozen=True)
class CalendarFreeBusyStatus:
    tenant_id: str
    calendar_id: str
    time_min: str
    time_max: str
    calendar_busy: bool
    available_slot_confirmed: bool = False
    booking_confirmed: bool = False
    action_authorized: bool = False


def verify_google_freebusy_readback(
    *, binding: ApprovedCalendarBinding, time_min: datetime,
    time_max: datetime, token: str, transport: CalendarReadTransport,
) -> CalendarFreeBusyStatus:
    """Free/busy is only occupancy evidence, not bookable inventory."""
    binding.check()
    if (time_min.tzinfo is None or time_min.utcoffset() is None
        or time_max.tzinfo is None or time_max.utcoffset() is None
        or time_max <= time_min or time_max - time_min > timedelta(hours=8)):
        raise CalendarVerificationError("invalid_calendar_freebusy_range")
    raw = transport.fetch(
        method="POST", path="/calendar/v3/freeBusy", token=token,
        body={
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": binding.calendar_id}],
        },
    )
    if not isinstance(raw, dict) or raw.get("kind") != "calendar#freeBusy":
        raise CalendarVerificationError("invalid_calendar_freebusy_response")
    calendars = raw.get("calendars")
    if not isinstance(calendars, dict) or set(calendars) != {binding.calendar_id}:
        raise CalendarVerificationError("calendar_freebusy_identity_mismatch")
    data = calendars[binding.calendar_id]
    if not isinstance(data, dict) or data.get("errors"):
        raise CalendarVerificationError("calendar_freebusy_provider_error")
    busy = data.get("busy")
    if not isinstance(busy, list) or len(busy) > 250:
        raise CalendarVerificationError("calendar_freebusy_interval_invalid")
    overlaps = False
    for entry in busy:
        if not isinstance(entry, dict):
            raise CalendarVerificationError("calendar_freebusy_interval_invalid")
        start, end = _aware(entry.get("start")), _aware(entry.get("end"))
        if end <= start:
            raise CalendarVerificationError("calendar_freebusy_interval_invalid")
        if start < time_max and end > time_min:
            overlaps = True
    return CalendarFreeBusyStatus(
        tenant_id=binding.tenant_id, calendar_id=binding.calendar_id,
        time_min=time_min.isoformat(), time_max=time_max.isoformat(),
        calendar_busy=overlaps,
    )
