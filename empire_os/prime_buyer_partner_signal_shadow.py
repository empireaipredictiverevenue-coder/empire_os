"""PRIME privacy-minimal original-owner partner signal triage (offline OBSERVE).

Input is caller-supplied, source-owner *metadata*, not an authenticated message.
No raw names/headers/body, mail/DB access, discovery, sending, inference of
buyer intent, approved traffic, payments or training. Scientific negative,
uncertain and outbound observations remain distinct from buying signals.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import re
from typing import Any

SCHEMA = "empire.prime.buyer_partner_signal_shadow.v1"
ALLOWED_SOURCE = frozenset({"empire_gmail_api_readonly", "connected_gmail_connector_read_only"})
# Exactly the original buyer_mail_semantics.EVENT_CODES as inspected on 2026-10-24.
TAXONOMY = {
    "LANDING_VISUAL_APPROVED_REPORTED": ("VISUAL_APPROVAL_REPORTED", "inbound"),
    "RECORDING_ENABLED_REPORTED": ("COMPLIANCE_STATE_REPORTED", "inbound"),
    "RECORDING_DISABLED_REPORTED": ("COMPLIANCE_STATE_REPORTED", "inbound"),
    "TEST_ENDED_BEFORE_CONNECTION_REPORTED": ("UNSUCCESSFUL_TEST_REPORTED", "inbound"),
    "ROUTE_OR_NUMBER_LIVE_REPORTED": ("TECHNICAL_STATUS_REPORTED", "inbound"),
    "CALLER_ID_PASSTHROUGH_REPORTED": ("TECHNICAL_STATUS_REPORTED", "inbound"),
    "PILOT_TECHNICAL_REQUIREMENTS_SENT": ("OUTBOUND_REQUIREMENTS_NOT_BUYER_RESPONSE", "outbound"),
    "COMPLETE_BUYER_REQUIREMENTS_SENT": ("OUTBOUND_REQUIREMENTS_NOT_BUYER_RESPONSE", "outbound"),
    "PUBLISHER_SPONSORED_PLACEMENTS_ONLY_REPORTED": ("NEGATIVE_COMMERCIAL_FIT_REPORTED", "inbound"),
    "BUYER_INTERNAL_DECISION_PENDING_REPORTED": ("INTERNAL_DECISION_PENDING_REPORTED", "inbound"),
    "ROOFING_BUYER_REVISED_COMMERCIAL_TERMS_REPORTED": ("TERMS_DISCUSSION_NOT_CONTRACT", "inbound"),
}
FIELDS = frozenset({"event_code", "direction", "observed_at", "message_fingerprint"})
HEX = re.compile(r"^[a-f0-9]{64}$")
MAX_ROWS = 150
MAX_AGE_DAYS = 45


def _moment(value: Any) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise ValueError("source_clock_required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("source_clock_invalid") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("source_clock_timezone_required")
    return stamp.astimezone(timezone.utc)


def review_partner_signal_codes(
    *, source: str, observations: Sequence[Mapping[str, Any]] | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Pure semantic-code research: never upgrades reports to real buyers.

    A message may have multiple DIFFERENT codes. Repeated same message/code
    or mismatched direction fails closed instead of multiplying evidence.
    """
    if type(source) is not str or source not in ALLOWED_SOURCE:
        raise ValueError("original_owner_gmail_metadata_source_required")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware_review_clock_required")
    now = as_of.astimezone(timezone.utc)
    if observations is not None and (
        type(observations) not in (list, tuple) or len(observations) > MAX_ROWS
    ):
        raise ValueError("bounded_original_owner_semantic_observations_required")
    counts: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    unique_messages = set()
    stale = 0
    for obs in observations or ():
        if type(obs) is not dict or set(obs) != FIELDS:
            raise ValueError("privacy_minimal_original_owner_observation_required")
        code = obs["event_code"]
        if type(code) is not str or code not in TAXONOMY:
            raise ValueError("unknown_original_owner_semantic_code")
        category, expected_direction = TAXONOMY[code]
        if obs["direction"] != expected_direction:
            raise ValueError("original_owner_direction_or_outbound_source_conflict")
        identity = obs["message_fingerprint"]
        if type(identity) is not str or not HEX.fullmatch(identity):
            raise ValueError("opaque_original_message_digest_required")
        key = (identity, code)
        if key in seen:
            raise ValueError("duplicate_owner_observation_not_independent_evidence")
        seen.add(key)
        unique_messages.add(identity)
        occurred = _moment(obs["observed_at"])
        if occurred > now + timedelta(minutes=5):
            raise ValueError("future_original_owner_observation")
        if now - occurred > timedelta(days=MAX_AGE_DAYS):
            stale += 1
        counts[category] += 1
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "source_state": "OWNER_METADATA_PRESENT_UNAUTHENTICATED" if observations is not None
                        else "OWNER_SOURCE_UNAVAILABLE_NOT_ZERO",
        "source_observation_count": len(observations) if observations is not None else None,
        "unique_message_count_not_verified_buyers": len(unique_messages) if observations is not None else None,
        "source_category_counts_unverified": dict(sorted(counts.items())),
        "stale_observation_count": stale if observations is not None else None,
        "negative_partner_evidence_preserved": True,
        "internal_decision_pending_not_approved": True,
        "technical_route_reports_not_connected_calls": True,
        "landing_visual_approval_not_traffic_admission": True,
        "outbound_requests_not_inbound_intent": True,
        "commercial_terms_discussion_not_binding_contract": True,
        "source_owner_authentication_verified": False,
        "independently_verified_buyer_enquiries": None,
        "accepted_commercial_terms_verified": False,
        "buyer_activation_authorized": False,
        "verified_paid_call_count": None,
        "realized_revenue_cents": None,
        "model_training_authorized": False,
        "database_writes": False,
        "outbound_sent": False,
        "trading_executed": False,
        "execution_authority": "none",
    }


def founder_partner_signal_status(review: Mapping[str, Any]) -> dict[str, Any]:
    """No original message identifiers or small cell counts to Founder."""
    if (type(review) is not dict or review.get("schema_version") != SCHEMA
        or review.get("execution_authority") != "none"
        or review.get("source_owner_authentication_verified") is not False
        or review.get("buyer_activation_authorized") is not False
        or review.get("realized_revenue_cents") is not None):
        raise ValueError("unpromoted_original_partner_shadow_review_required")
    n = review.get("source_observation_count")
    categories = review.get("source_category_counts_unverified")
    if n is not None and (type(n) is not int or not 0 <= n <= MAX_ROWS):
        raise ValueError("bounded_unverified_partner_count_required")
    if type(categories) is not dict or any(
        k not in {v[0] for v in TAXONOMY.values()}
        or type(v) is not int or v <= 0 or v > MAX_ROWS
        for k, v in categories.items()
    ) or sum(categories.values()) != (n if n is not None else 0):
        raise ValueError("untrusted_partner_category_projection")
    return {
        "schema_version": "empire.prime.founder_partner_signal_status.v1",
        "mode": "OBSERVE",
        "observed_reported_event_count_band": (
            f"{(n//5)*5}-{(n//5)*5+4}" if n is not None else None
        ),
        "category_count_band_when_at_least_five": {
            k: f"{(v//5)*5}-{(v//5)*5+4}"
            for k, v in sorted(categories.items()) if v >= 5
        },
        "less_than_five_category_counts_suppressed": True,
        "buyer_enquiries_independently_verified": False,
        "negative_and_pending_partner_evidence_preserved": True,
        "owner_source_live_authenticated": False,
        "revenue_recognized": False,
        "outbound_sent": False,
        "execution_authority": "none",
        "status": "ORIGINAL_PARTNER_SEMANTIC_RESEARCH_ONLY",
    }
