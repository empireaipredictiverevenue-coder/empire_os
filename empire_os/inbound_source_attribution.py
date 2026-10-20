"""Provider-linked, tenant-scoped source attribution for recovered inbound calls.

Sources are FIRST-PARTY verified call-tracking joins, never guessed from
keywords, model output or referrer strings. Offline contract only; no ad spend.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from empire_os.inbound_revenue_recovery import (
    MISSED_STATUSES, RecoveryEvent, active_calendar_confirmations,
)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class SourceTouch:
    tenant_id: str
    call_id: str
    touch_id: str
    occurred_at: str
    channel: str
    source_ref: str
    attested_by: str = "unverified"
    verified: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        for key in ("tenant_id", "call_id", "touch_id"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key}_required")
        if self.channel not in {
            "organic_search", "paid_search", "paid_social", "organic_social",
            "referral", "direct", "email", "marketplace", "other",
        }:
            raise ValueError("unsupported_attribution_channel")
        if self.attested_by not in {
            "first_party_call_tracking", "verified_partner_reference", "unverified",
        }:
            raise ValueError("unsupported_touch_attestor")
        if not isinstance(self.verified, bool) or not isinstance(self.synthetic, bool):
            raise ValueError("invalid_touch_evidence_flags")
        if self.verified and (
            self.attested_by == "unverified" or not str(self.source_ref).strip()
        ):
            raise ValueError("verified_touch_requires_primary_source_evidence")
        try:
            stamp = _ts(self.occurred_at)
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("time_zone_required")
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("invalid_touch_timestamp") from exc


def attribute_recovered_sources(
    events: list[RecoveryEvent] | tuple[RecoveryEvent, ...],
    touches: list[SourceTouch] | tuple[SourceTouch, ...],
    *,
    tenant_id: str,
    as_of: datetime,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Group source-attributed recovered calls and verified payment receipts.

    Unknown/unlinked sources are tracked explicitly. No extrapolation from
    attribution rates to money, and no claim that paid clicks drove a sale.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id_required")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("aware_as_of_required")
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or not 1 <= lookback_days <= 90:
        raise ValueError("invalid_lookback_days")

    event_keys: dict[tuple[str, str], RecoveryEvent] = {}
    for e in events:
        if not isinstance(e, RecoveryEvent):
            raise ValueError("invalid_recovery_event")
        if e.tenant_id != tenant_id or e.synthetic or _ts(e.occurred_at) > as_of:
            continue
        key = (e.tenant_id, e.event_id)
        if key in event_keys and event_keys[key] != e:
            raise ValueError("conflicting_duplicate_event_id")
        event_keys[key] = e
    calls: dict[str, list[RecoveryEvent]] = {}
    for e in event_keys.values():
        calls.setdefault(e.call_id, []).append(e)

    touch_keys: dict[str, SourceTouch] = {}
    ignored_touches = 0
    for t in touches:
        if not isinstance(t, SourceTouch):
            raise ValueError("invalid_source_touch")
        if t.tenant_id != tenant_id or t.synthetic or _ts(t.occurred_at) > as_of:
            continue
        if t.touch_id in touch_keys:
            if touch_keys[t.touch_id] != t:
                raise ValueError("conflicting_duplicate_touch_id")
            continue
        touch_keys[t.touch_id] = t
        if not t.verified or t.attested_by == "unverified":
            ignored_touches += 1

    linked_touches: dict[str, list[SourceTouch]] = {}
    for t in touch_keys.values():
        if not t.verified or t.attested_by == "unverified":
            continue
        linked_touches.setdefault(t.call_id, []).append(t)

    channels: dict[str, dict[str, Any]] = {}
    first_touch_distribution: dict[str, int] = {}
    receipt_seen: set[tuple[str, str]] = set()
    missed = recovered = attributed = 0
    for call_id, call_events in sorted(calls.items()):
        call_events.sort(key=lambda e: (_ts(e.occurred_at), e.event_id))
        missed_events = [
            e for e in call_events if e.kind in MISSED_STATUSES
            and e.origin == "provider" and e.verified
        ]
        if not missed_events:
            continue
        missed += 1
        first_missed = _ts(missed_events[0].occurred_at)
        if any(e.kind == "followup_opt_out" for e in call_events):
            continue
        active = active_calendar_confirmations(call_events)
        qualifying = [
            e for e in call_events
            if (e.kind == "callback_connected" or
                (e.kind == "booking_confirmed" and active.get(e.evidence_ref) == e))
            and e.verified and e.evidence_ref and _ts(e.occurred_at) > first_missed
        ]
        if not qualifying:
            continue
        recovered += 1
        recovery_time = min(_ts(e.occurred_at) for e in qualifying)
        eligible_touches = sorted([
            t for t in linked_touches.get(call_id, [])
            if first_missed - timedelta(days=lookback_days) <= _ts(t.occurred_at) <= first_missed
        ], key=lambda t: (_ts(t.occurred_at), t.touch_id))
        channel = eligible_touches[-1].channel if eligible_touches else "unattributed"
        if eligible_touches:
            attributed += 1
            first_channel = eligible_touches[0].channel
            first_touch_distribution[first_channel] = first_touch_distribution.get(first_channel, 0) + 1
        bucket = channels.setdefault(channel, {
            "recovered_calls": 0,
            "verified_paid_minor_by_currency": {},
            "classification": (
                "verified_first_party_source" if eligible_touches else "unknown_source"
            ),
        })
        bucket["recovered_calls"] += 1
        for e in call_events:
            if e.kind != "invoice_paid" or not e.verified or _ts(e.occurred_at) < recovery_time:
                continue
            receipt_key = (e.origin, e.evidence_ref)
            if receipt_key in receipt_seen:
                continue
            receipt_seen.add(receipt_key)
            money = bucket["verified_paid_minor_by_currency"]
            money[e.currency] = money.get(e.currency, 0) + (e.amount_minor or 0)

    return {
        "tenant_id": tenant_id,
        "as_of": as_of.isoformat(),
        "mode": "offline_verified_source_contract_only",
        "missed_calls_with_verified_provider_disposition": missed,
        "recovered_calls": recovered,
        "recovered_calls_with_verified_source": attributed,
        "recovered_calls_without_verified_source": recovered - attributed,
        "ignored_unverified_source_touches": ignored_touches,
        "last_touch_channels": dict(sorted(channels.items())),
        "first_touch_recovered_call_counts": dict(sorted(first_touch_distribution.items())),
        "source_inference_permitted": False,
        "ad_spend_inferred": False,
        "profit_or_roi_inferred": False,
        "outbound_sent": False,
    }
