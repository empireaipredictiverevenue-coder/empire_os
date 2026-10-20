"""Offline measurement of Meta Market Validation pilots.

Numbers imported from packet are unverified aggregate reports, NEVER authenticated
revenue or customer outcomes. Canonical owners must reconcile separately.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "empire.meta_social_pilot_telemetry.v1"
METRIC_FIELDS = (
    "eligible_landing_visits",
    "opted_in_enquiries",
    "qualified_enquiries",
    "payer_accepted_appointments",
    "settled_payouts",
)
FORBIDDEN = frozenset({
    "user_id", "name", "person_name", "email", "phone", "ip_address",
    "cookie", "profile_url", "source_user", "message_body", "raw_text",
    "credit_card", "payment_identifier", "payout_account",
})


def assess_telemetry(packet: Mapping[str, Any] | None, lane_ids: set[str]) -> dict[str, Any]:
    """Aggregate-only pilot readback and stop signals, not a live analytics connector."""
    if packet is None:
        return {"status": "NO_FIRST_PARTY_TELEMETRY", "source": "none",
                "metrics_authenticated": False, "revenue_verified": False,
                "lanes": [], "next_action": "COLLECT_PERMISSIONED_OWNED_FUNNEL_EVENTS_AFTER_APPROVAL"}
    if not isinstance(packet, Mapping) or packet.get("schema_version") != SCHEMA:
        raise ValueError("unsupported_pilot_telemetry_schema")
    if packet.get("synthetic") is True:
        return {"status": "SYNTHETIC_MEASUREMENT_REHEARSAL_ONLY",
                "metrics_authenticated": False, "revenue_verified": False,
                "lanes": [], "next_action": "AWAIT_REAL_FIRST_PARTY_TELEMETRY"}
    rows = packet.get("lanes")
    if not isinstance(rows, list) or len(rows) > 5:
        raise ValueError("invalid_pilot_telemetry_lanes")
    results = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_pilot_telemetry_row")
        if any(str(k).casefold() in FORBIDDEN for k in row):
            raise ValueError("personal_data_not_allowed_in_pilot_telemetry")
        lane_id = row.get("lane_id")
        if lane_id not in lane_ids or lane_id in seen:
            raise ValueError("unknown_or_duplicate_pilot_lane")
        seen.add(lane_id)
        values = []
        for name in METRIC_FIELDS:
            value = row.get(name)
            if type(value) is not int or not 0 <= value <= 100_000:
                raise ValueError("invalid_pilot_metric_" + name)
            values.append(value)
        # Aggregate event counts cannot grow down an ordinary qualification funnel.
        if values != sorted(values, reverse=True):
            raise ValueError("non_monotonic_pilot_funnel")
        visits, opted_in, qualified, appointments, payouts = values
        # These are simple diagnostics, never evidence of an actual commission.
        opt_in_per_visit = round(opted_in / visits, 4) if visits else None
        accepted_per_qualified = round(appointments / qualified, 4) if qualified else None
        if visits >= 100 and opted_in == 0:
            signal = "REVIEW_STOP_ZERO_CONVERSION"
        elif visits >= 100 and opt_in_per_visit is not None and opt_in_per_visit < 0.02:
            signal = "REVIEW_WEAK_OFFER_OR_AUDIENCE"
        elif payouts > 0:
            signal = "CLAIMED_PAYOUT_REQUIRES_CANONICAL_RECONCILIATION"
        else:
            signal = "NEED_MORE_EVIDENCE"
        results.append({
            "lane_id": lane_id,
            "imported_aggregate_counts_unverified": dict(zip(METRIC_FIELDS, values)),
            "reported_opt_in_rate_not_verified": opt_in_per_visit,
            "reported_appointment_acceptance_rate_not_verified": accepted_per_qualified,
            "learning_signal": signal,
            "actual_appointments_independently_verified": False,
            "actual_payouts_independently_verified": False,
            "authorised_to_scale": False,
        })
    return {
        "status": "UNVERIFIED_AGGREGATE_REPORT_FOR_REVIEW",
        "source": "operator_supplied_offline_packet",
        "metrics_authenticated": False, "revenue_verified": False,
        "lanes": sorted(results, key=lambda r: r["lane_id"]),
        "next_action": "RECONCILE_WITH_CANONICAL_CRM_CONSENT_AND_PAYOUT_OWNERS",
    }
