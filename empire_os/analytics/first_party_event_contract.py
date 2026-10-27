"""Strict, privacy-minimising first-party event contract and offline aggregate.

NOT a live collector. No cookies, HTTP route, token minting, DB writes,
Google provider, network, marketing outbound, or revenue authority.
Neither browser-side consent flags nor prospect/email consent count as
website analytics consent; it must be resolved by a future trusted server
consent ledger before each event is accepted.

Events are opaque and never returned; only anonymous category counts
can leave this module, always labelled SIMULATION_ONLY until a separate
approved, audited real observation path exists.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

SCHEMA = "empire.analytics.first_party_event_contract.v1"
ALLOWED_EVENTS = frozenset({
    "page_view", "engagement", "cta_click",
    "form_start", "form_submit_attempt",
})
ALLOWED_CHANNELS = frozenset({
    "direct", "organic_search", "organic_social",
    "email", "referral", "unknown",
})
REQUIRED_KEYS = frozenset({
    "event_nonce", "session_nonce", "event_type", "occurred_at",
    "page_path",
})
_NONCE = re.compile(r"^[0-9a-f]{32}$")
# Only static, confirmed owner routes may be included in approved_paths.
_SAFE_PATH = re.compile(r"^/(?:[a-z][a-z0-9-]{0,48}/?){0,6}$")
MAX_BATCH = 500
MAX_AGE = timedelta(hours=48)
MAX_FUTURE = timedelta(minutes=1)


class EventContractHeld(ValueError):
    """A source, privacy, consent or bounded aggregate gate is not proven."""


@dataclass(frozen=True)
class _Event:
    event_nonce: str
    session_nonce: str
    event_type: str
    occurred_at: datetime
    page_path: str


def _approved_paths(paths: Any) -> frozenset[str]:
    if (not isinstance(paths, (frozenset, set, tuple, list))
            or isinstance(paths, (str, bytes)) or not 1 <= len(paths) <= 50):
        raise EventContractHeld("ANALYTICS_APPROVED_PAGE_REGISTER_MISSING")
    if (any(type(p) is not str or not _SAFE_PATH.fullmatch(p)
            or "?" in p or "#" in p or "//" in p for p in paths)):
        raise EventContractHeld("ANALYTICS_APPROVED_PAGE_REGISTER_INVALID")
    return frozenset(paths)


def _parse_event(raw: Any, *, paths: frozenset[str],
                 now: datetime) -> _Event:
    if not isinstance(raw, Mapping) or set(raw) != REQUIRED_KEYS:
        raise EventContractHeld("ANALYTICS_EVENT_FIELDS_NOT_ALLOWLISTED")
    for field in ("event_nonce", "session_nonce"):
        if (type(raw[field]) is not str or not _NONCE.fullmatch(raw[field])
                or raw[field] == "0" * 32):
            raise EventContractHeld("ANALYTICS_EVENT_NONCE_INVALID")
    if type(raw["event_type"]) is not str or raw["event_type"] not in ALLOWED_EVENTS:
        raise EventContractHeld("ANALYTICS_EVENT_NAME_NOT_ALLOWLISTED")
    if type(raw["page_path"]) is not str or raw["page_path"] not in paths:
        raise EventContractHeld("ANALYTICS_PAGE_PATH_NOT_REGISTERED")
    ts = raw["occurred_at"]
    if type(ts) is not str or len(ts) != 20 or not ts.endswith("Z"):
        raise EventContractHeld("ANALYTICS_EVENT_TIMESTAMP_INVALID")
    try:
        occurred = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise EventContractHeld("ANALYTICS_EVENT_TIMESTAMP_INVALID") from None
    if not (now - MAX_AGE <= occurred <= now + MAX_FUTURE):
        raise EventContractHeld("ANALYTICS_EVENT_WINDOW_EXCEEDED")
    return _Event(**{**{k:raw[k] for k in (
        "event_nonce", "session_nonce", "event_type",
        "page_path")},
        "occurred_at":occurred})


def _verified_simulated_events(
    events: Sequence[Mapping[str, Any]],
    *,
    approved_paths: Sequence[str],
    resolve_server_consent: Callable[[str], bool] | None,
    resolve_server_channel: Callable[[str], str] | None,
    now: datetime | None,
) -> tuple[list[_Event], dict[str, str], int]:
    """One shared validation pass; never return unverified partial cohorts."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise EventContractHeld("ANALYTICS_SERVER_CLOCK_UNVERIFIED")
    now = now.astimezone(timezone.utc)
    paths = _approved_paths(approved_paths)
    if (isinstance(events, (str, bytes, Mapping))
            or not isinstance(events, Sequence)
            or not 1 <= len(events) <= MAX_BATCH):
        raise EventContractHeld("ANALYTICS_BATCH_BOUNDS_INVALID")
    if resolve_server_consent is None or not callable(resolve_server_consent):
        raise EventContractHeld("ANALYTICS_SERVER_CONSENT_RESOLVER_REQUIRED")
    if resolve_server_channel is None or not callable(resolve_server_channel):
        raise EventContractHeld("ANALYTICS_SERVER_ACQUISITION_RESOLVER_REQUIRED")
    parsed = [_parse_event(row, paths=paths, now=now) for row in events]
    seen_nonce: dict[str, _Event] = {}
    for item in parsed:
        previous = seen_nonce.get(item.event_nonce)
        if previous is not None and previous != item:
            raise EventContractHeld("ANALYTICS_EVENT_REPLAY_CONFLICT")
        seen_nonce[item.event_nonce] = item
    deduplicated = list(seen_nonce.values())
    sessions = {event.session_nonce for event in deduplicated}
    # One entire-batch deny when any consent or source resolver is unavailable.
    channel_for_session: dict[str, str] = {}
    for session in sessions:
        try:
            approved = resolve_server_consent(session)
        except Exception:
            raise EventContractHeld("ANALYTICS_CONSENT_LEDGER_UNAVAILABLE") from None
        if approved is not True:
            raise EventContractHeld("ANALYTICS_WEBSITE_CONSENT_NOT_PROVEN")
        try:
            channel = resolve_server_channel(session)
        except Exception:
            raise EventContractHeld("ANALYTICS_ACQUISITION_LEDGER_UNAVAILABLE") from None
        if type(channel) is not str or channel not in ALLOWED_CHANNELS:
            raise EventContractHeld("ANALYTICS_SERVER_CHANNEL_UNVERIFIED")
        channel_for_session[session] = channel
    return deduplicated, channel_for_session, len(parsed) - len(deduplicated)


def simulate_verified_batch(
    events: Sequence[Mapping[str, Any]],
    *,
    approved_paths: Sequence[str],
    resolve_server_consent: Callable[[str], bool] | None,
    resolve_server_channel: Callable[[str], str] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fail closed before returning aggregate-only simulated metrics.

    The consent callback represents an independent, trusted *website*
    analytics consent ledger. A browser-supplied flag is expressly not
    acceptable; events containing one are rejected by the exact schema.
    Event/session nonces and per-page paths are NEVER returned.
    """
    deduplicated, channel_for_session, retries_discarded = _verified_simulated_events(
        events, approved_paths=approved_paths,
        resolve_server_consent=resolve_server_consent,
        resolve_server_channel=resolve_server_channel, now=now,
    )
    counts = Counter(event.event_type for event in deduplicated)
    engaged = {item.session_nonce for item in deduplicated
               if item.event_type == "engagement"}
    return {
        "schema_version": SCHEMA,
        "status": "OFFLINE_CONSENT_GATED_CONTRACT_SIMULATION",
        "mode": "SIMULATION_ONLY",
        "observed_live_sessions_verified": False,
        "consent_source": "injected_server_side_resolver_simulated",
        "acquisition_source_authority": "injected_server_side_resolver_simulated",
        "simulated_sessions": len(channel_for_session),
        "simulated_page_views": counts["page_view"],
        "simulated_engaged_sessions": len(engaged),
        "simulated_cta_clicks": counts["cta_click"],
        "simulated_form_starts": counts["form_start"],
        "simulated_form_submit_attempts": counts["form_submit_attempt"],
        "accepted_event_count": len(deduplicated),
        "duplicate_retries_discarded": retries_discarded,
        "real_visitors_verified": False,
        "real_leads_verified": False,
        "crm_conversion_verified": False,
        "realised_revenue_verified": False,
        "revenue_attribution_verified": False,
        "browser_collector_enabled": False,
        "production_ingestion_enabled": False,
        "database_writes": False,
        "outbound_sent": False,
        "paid_provider_requests": False,
        "execution_authority": "NONE",
    }


MIN_CHANNEL_COHORT = 5


def simulate_channel_stage_presence(
    events: Sequence[Mapping[str, Any]],
    *,
    approved_paths: Sequence[str],
    resolve_server_consent: Callable[[str], bool] | None,
    resolve_server_channel: Callable[[str], str] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Offline-only six-channel stage-presence review; never a live conversion.

    One event is not a lead, one form submit ATTEMPT is not a successful
    submission, and a visitor reaching stage B need not have visited A in
    the bounded batch. No session identifiers, paths or source URLs escape.
    The minimum cohort is a display guard, NOT a production privacy proof.
    """
    deduplicated, channels, retries_discarded = _verified_simulated_events(
        events, approved_paths=approved_paths,
        resolve_server_consent=resolve_server_consent,
        resolve_server_channel=resolve_server_channel, now=now,
    )
    per_channel_sessions: dict[str, set[str]] = {
        name: set() for name in ALLOWED_CHANNELS
    }
    stage_sessions: dict[str, dict[str, set[str]]] = {
        name: {stage: set() for stage in ALLOWED_EVENTS}
        for name in ALLOWED_CHANNELS
    }
    for session, channel in channels.items():
        per_channel_sessions[channel].add(session)
    for e in deduplicated:
        stage_sessions[channels[e.session_nonce]][e.event_type].add(e.session_nonce)

    rows = []
    suppressed = 0
    for channel in sorted(ALLOWED_CHANNELS):
        size = len(per_channel_sessions[channel])
        disclosed = size >= MIN_CHANNEL_COHORT
        if size and not disclosed:
            suppressed += 1
        rows.append({
            "channel": channel,
            "status": ("SIMULATED_DISPLAYABLE_COHORT" if disclosed
                       else "SUPPRESSED_SMALL_SIMULATED_COHORT" if size
                       else "NO_SIMULATED_EVENTS"),
            "simulated_unique_sessions": size if disclosed else None,
            "simulated_sessions_with_stage": (
                {stage: len(stage_sessions[channel][stage])
                 for stage in sorted(ALLOWED_EVENTS)}
                if disclosed else None
            ),
            "form_submit_attempt_is_confirmed_lead": False,
            "revenue_attributed": False,
        })
    return {
        "schema_version": "empire.analytics.offline_channel_stage_presence.v1",
        "status": "OFFLINE_CHANNEL_AGGREGATION_SIMULATION",
        "mode": "SIMULATION_ONLY",
        "original_contract": SCHEMA,
        "original_allowlisted_channel_count": len(ALLOWED_CHANNELS),
        "original_allowlisted_stage_count": len(ALLOWED_EVENTS),
        "minimum_disclosure_cohort": MIN_CHANNEL_COHORT,
        "small_cohorts_suppressed_count": suppressed,
        # Hide global totals too when they could reveal a suppressed cohort
        # through subtraction from the disclosed channel rows.
        "simulated_accepted_event_count": (
            len(deduplicated) if not suppressed else None
        ),
        "simulated_duplicate_retries_discarded": (
            retries_discarded if not suppressed else None
        ),
        "channels": rows,
        "display_guard_is_not_legal_privacy_certification": True,
        "stage_presence_is_not_ordered_conversion_funnel": True,
        "session_source_resolved_once_via_server_simulation": True,
        "actual_source_attribution_verified": False,
        "actual_sessions_verified": False,
        "actual_leads_verified": False,
        "crm_or_finance_join_verified": False,
        "actual_revenue_verified": False,
        "paid_campaign_execution_authorized": False,
        "website_collector_enabled": False,
        "runtime_ingestion_enabled": False,
        "new_database_or_agent_created": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }
