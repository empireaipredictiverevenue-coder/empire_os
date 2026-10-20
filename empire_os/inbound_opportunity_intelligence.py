"""Evidence-grounded, offline inbound opportunity prioritisation.

No caller identities, LLM assumptions, fabricated deal values or auto actions.
A "ticket" represents one canonical provider call ID, *not* a unique person.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from empire_os.inbound_business_hours import BusinessHoursPolicy, staffed_hours_status
from empire_os.inbound_revenue_recovery import MISSED_STATUSES, RecoveryEvent


def _stamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of_must_be_timezone_aware")


@dataclass(frozen=True)
class OpportunityPolicy:
    tenant_id: str
    callback_sla_minutes: int = 30
    booking_sla_minutes: int = 20
    general_sla_minutes: int = 120
    stale_after_hours: int = 72
    max_tickets: int = 500

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("tenant_id_required")
        for attr, limit in (
            ("callback_sla_minutes", 1440),
            ("booking_sla_minutes", 1440),
            ("general_sla_minutes", 1440),
            ("stale_after_hours", 24 * 90),
            ("max_tickets", 5000),
        ):
            value = getattr(self, attr)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= limit:
                raise ValueError("invalid_opportunity_policy")


@dataclass(frozen=True)
class OpportunitySignal:
    """Human-attested signal; model-only claims cannot raise commercial priority."""
    tenant_id: str
    call_id: str
    signal_id: str
    observed_at: str
    kind: str  # booking_intent, pricing_request, service_issue, urgent_need
    origin: str  # human_reviewed, model_candidate
    evidence_ref: str
    human_confirmed: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        for attr in ("tenant_id", "call_id", "signal_id"):
            value = getattr(self, attr)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{attr}_required")
        if self.kind not in {
            "booking_intent", "pricing_request", "service_issue", "urgent_need"
        }:
            raise ValueError("unsupported_signal_kind")
        if self.origin not in {"human_reviewed", "model_candidate"}:
            raise ValueError("unsupported_signal_origin")
        if not isinstance(self.human_confirmed, bool) or not isinstance(self.synthetic, bool):
            raise ValueError("invalid_signal_flags")
        if self.human_confirmed and self.origin != "human_reviewed":
            raise ValueError("human_confirmation_requires_human_origin")
        if self.human_confirmed and not str(self.evidence_ref).strip():
            raise ValueError("human_confirmation_requires_evidence")
        try:
            _aware(_stamp(self.observed_at))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("invalid_signal_timestamp") from exc


def build_opportunity_queue(
    events: list[RecoveryEvent] | tuple[RecoveryEvent, ...],
    *,
    policy: OpportunityPolicy,
    as_of: datetime,
    business_hours: BusinessHoursPolicy | None = None,
    signals: list[OpportunitySignal] | tuple[OpportunitySignal, ...] = (),
) -> dict[str, Any]:
    """Rank open missed-call work for *human review only*.

    Verified real-provider terminal dispositions are required. Internal queue
    hints are not permission to call/text, alter bookings or claim revenue.
    """
    _aware(as_of)
    if business_hours is not None and business_hours.tenant_id != policy.tenant_id:
        raise ValueError("business_hours_tenant_mismatch")
    dedup: dict[tuple[str, str], RecoveryEvent] = {}
    for e in events:
        if not isinstance(e, RecoveryEvent):
            raise ValueError("invalid_recovery_event")
        if e.tenant_id != policy.tenant_id or e.synthetic or _stamp(e.occurred_at) > as_of:
            continue
        key = (e.tenant_id, e.event_id)
        if key in dedup and dedup[key] != e:
            raise ValueError("conflicting_duplicate_event_id")
        dedup[key] = e
    calls: dict[str, list[RecoveryEvent]] = {}
    for e in dedup.values():
        calls.setdefault(e.call_id, []).append(e)

    trusted_signals: dict[str, list[OpportunitySignal]] = {}
    unverified_signals_count = 0
    seen_signal_ids: dict[str, OpportunitySignal] = {}
    for s in signals:
        if not isinstance(s, OpportunitySignal):
            raise ValueError("invalid_opportunity_signal")
        if s.tenant_id != policy.tenant_id or s.synthetic or _stamp(s.observed_at) > as_of:
            continue
        if s.signal_id in seen_signal_ids:
            if seen_signal_ids[s.signal_id] != s:
                raise ValueError("conflicting_duplicate_signal_id")
            continue
        seen_signal_ids[s.signal_id] = s
        if not s.human_confirmed or s.origin != "human_reviewed":
            unverified_signals_count += 1
            continue
        trusted_signals.setdefault(s.call_id, []).append(s)

    hours = staffed_hours_status(business_hours, as_of) if business_hours else None
    staffing = (
        "verified_open" if hours and hours.open_now is True else
        "verified_closed" if hours and hours.open_now is False else
        "unknown"
    )
    tickets: list[dict[str, Any]] = []
    suppressed = recovered = aged_out = unverified_missed = 0
    for call_id, call_events in calls.items():
        ordered = sorted(call_events, key=lambda e: (_stamp(e.occurred_at), e.event_id))
        missed = [
            e for e in ordered
            if e.kind in MISSED_STATUSES and e.verified and e.origin == "provider"
        ]
        if not missed:
            unverified_missed += int(any(e.kind in MISSED_STATUSES for e in ordered))
            continue
        missed_event = missed[0]
        start = _stamp(missed_event.occurred_at)
        following = [e for e in ordered if _stamp(e.occurred_at) > start]
        # Any explicit opt-out after the missed event suppresses the prospect's
        # **call-level** ticket; this is NOT a global phone suppression write.
        if any(e.kind == "followup_opt_out" for e in ordered):
            suppressed += 1
            continue
        if any(
            e.kind in {"callback_connected", "booking_confirmed"}
            and e.verified and e.evidence_ref for e in following
        ):
            recovered += 1
            continue

        age_seconds = (as_of - start).total_seconds()
        if age_seconds > policy.stale_after_hours * 3600:
            aged_out += 1
            continue

        callback = any(e.kind == "callback_requested" for e in following)
        booking = any(e.kind == "booking_requested" for e in following)
        escalated = any(e.kind == "human_transfer" for e in following)
        verified_signals = [
            s for s in trusted_signals.get(call_id, [])
            if _stamp(s.observed_at) >= start
        ]
        kinds = sorted({s.kind for s in verified_signals})
        high_urgency = "urgent_need" in kinds
        if booking:
            sla = policy.booking_sla_minutes
            next_action = "operator_review_booking_request"
            base_score = 65
        elif callback:
            sla = policy.callback_sla_minutes
            next_action = "operator_review_callback_request"
            base_score = 55
        elif escalated or "service_issue" in kinds:
            sla = policy.callback_sla_minutes
            next_action = "operator_review_service_issue"
            base_score = 60
        else:
            sla = policy.general_sla_minutes
            next_action = "operator_triage_missing_call"
            base_score = 30
        due_at = start + timedelta(minutes=sla)
        overdue = as_of >= due_at
        # Scoring is explicitly rules-based, not predictive revenue.
        priority_score = min(100, base_score
            + (20 if high_urgency else 0)
            + (10 if "pricing_request" in kinds else 0)
            + (10 if overdue else 0))
        priority = (
            "urgent_review" if high_urgency or priority_score >= 75 else
            "high" if priority_score >= 55 else "normal"
        )
        tickets.append({
            "tenant_id": policy.tenant_id,
            "call_id": call_id,
            "missed_at": start.isoformat(),
            "due_at": due_at.isoformat(),
            "age_minutes": int(age_seconds // 60),
            "sla_target_minutes": sla,
            "sla_overdue_wall_clock": overdue,
            "staffing_status": staffing,
            "staffing_verified": staffing != "unknown",
            "priority": priority,
            "priority_score": priority_score,
            "priority_explanation": [
                "verified_missed_call",
                *([ "booking_requested" ] if booking else []),
                *([ "callback_requested" ] if callback else []),
                *([ "human_transfer_observed" ] if escalated else []),
                *([ "human_confirmed_" + kind for kind in kinds ]),
                *([ "wall_clock_sla_overdue" ] if overdue else []),
            ],
            "suggested_internal_action": next_action,
            "outbound_authorized": False,
            "booking_authorized": False,
            "payment_authorized": False,
            "actual_revenue_inferred": False,
            "human_review_required": True,
            "evidence_event_ids": [e.event_id for e in ordered],
            "human_confirmed_signal_count": len(verified_signals),
        })

    tickets.sort(key=lambda t: (
        -t["priority_score"], -int(t["sla_overdue_wall_clock"]),
        t["missed_at"], t["call_id"],
    ))
    overflow = max(0, len(tickets) - policy.max_tickets)
    return {
        "tenant_id": policy.tenant_id,
        "mode": "offline_human_review_only",
        "as_of": as_of.isoformat(),
        "staffing_status": staffing,
        "next_staffed_open_at": hours.next_open_at if hours else None,
        "tickets": tickets[:policy.max_tickets],
        "queue_total": len(tickets),
        "queue_returned": min(len(tickets), policy.max_tickets),
        "overflow_count": overflow,
        "already_recovered_calls": recovered,
        "opted_out_calls_excluded": suppressed,
        "stale_calls_excluded": aged_out,
        "unverified_missed_events_excluded": unverified_missed,
        "unverified_model_signals_ignored": unverified_signals_count,
        "outbound_sent": False,
        "customer_contact_authorized": False,
        "revenue_inferred": False,
    }
