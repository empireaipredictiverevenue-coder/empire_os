"""Existing Sales Director owner: review buyer-offer correspondence, not CRM.

A read-only, in-process decision contract for authentic external buyer replies.
Claims/IDs passed by a caller are NOT authenticated here. Commercial owner
must reconcile actual mailbox message headers and suppression at the source.
No Gmail access, contact dispatch, offer acceptance, account onboarding, site
mutation, lead creation, booking, traffic switch, finance or forecasts.

Uses *separate* observed per-buyer programmes. Cannot borrow geo/payout/ZIPs
or legal/source rights from another buyer. No per-call revenue is recognized.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

SCHEMA = "empire.revenue_first.buyer_offer_triage.v1"
MAX_BUYERS = 8
MAX_REPLIES = 12
MAX_CENTS = 1_000_000

REPLY_STATES = frozenset({
    "BUYER_REVIEW_OPEN",
    "BUYER_PILOT_TERMS_PROPOSED",
    "BUYER_DIRECT_ROUTE_TESTED_CLAIM",
    "BUYER_ONBOARDING_PAUSED",
    "BUYER_APPLICATION_REQUIRED",
})
VERTICALS = frozenset({"roofing", "garage_door_repair", "property_intelligence"})
MARKETS = frozenset({"US", "UK"})
PROGRAMMES = frozenset({"PAY_PER_CALL", "B2B_INTELLIGENCE"})
FIELDS = frozenset({
    "buyer_key", "market", "vertical", "programme", "message_claims",
    "proposed_payout_cents", "payout_currency", "candidate_source_exists",
    "independently_verified_qualified_demand", "review_owner",
})
REPLY_FIELDS = frozenset({"message_ref", "received_at", "claim"})


def _text(value: Any, field: str, *, length: int = 100) -> str:
    if type(value) is not str or not 1 <= len(value.strip()) <= length:
        raise ValueError(f"{field}: required bounded text")
    return value.strip()


def _time(value: Any, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{field}: invalid timestamp") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field}: timezone required")
    return value.astimezone(timezone.utc)


def review_buyer_offer(
    row: Mapping[str, Any], *, as_of: datetime,
) -> dict[str, Any]:
    """Produce founder-review tasks, NEVER buyer eligibility or spend."""
    now = _time(as_of, "as_of")
    if not isinstance(row, Mapping) or set(row) != FIELDS:
        raise ValueError("exact buyer-offer review fields required")
    key = _text(row["buyer_key"], "buyer_key", length=64).casefold()
    if not all(c.isascii() and (c.isalnum() or c in "_-.") for c in key):
        raise ValueError("opaque buyer key only")
    market = row["market"]
    vertical = row["vertical"]
    programme = row["programme"]
    if market not in MARKETS or vertical not in VERTICALS or programme not in PROGRAMMES:
        raise ValueError("unsupported market/vertical/programme")
    if (programme == "B2B_INTELLIGENCE") != (vertical == "property_intelligence"):
        raise ValueError("buyer programme and product family mismatch")
    owner = _text(row["review_owner"], "review_owner", length=80)
    if owner not in {"sales_director_operator", "commercial_evidence_verifier"}:
        raise ValueError("existing commercial owner required")
    proposed = row["proposed_payout_cents"]
    currency = row["payout_currency"]
    if proposed is not None:
        if type(proposed) is not int or not 1 <= proposed <= MAX_CENTS or currency != "USD":
            raise ValueError("positive USD minor-unit quote required")
        if programme != "PAY_PER_CALL":
            raise ValueError("cannot assign PPC payout to B2B pilot product")
    elif currency is not None:
        raise ValueError("currency must be unknown when payout is unknown")
    if type(row["candidate_source_exists"]) is not bool:
        raise ValueError("candidate source presence must be explicit boolean")
    if type(row["independently_verified_qualified_demand"]) is not bool:
        raise ValueError("demand observation must be explicit boolean")
    claims = row["message_claims"]
    if type(claims) not in (list, tuple) or len(claims) > MAX_REPLIES:
        raise ValueError("bounded message receipt summaries required")
    states: set[str] = set()
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, Mapping) or set(claim) != REPLY_FIELDS:
            raise ValueError("exact bounded buyer reply fields required")
        ref = _text(claim["message_ref"], "message_ref", length=128)
        if ref in seen:
            raise ValueError("duplicate buyer reply reference")
        seen.add(ref)
        received = _time(claim["received_at"], "received_at")
        if received > now:
            raise ValueError("future buyer reply")
        state = claim["claim"]
        if type(state) is not str or state not in REPLY_STATES:
            raise ValueError("unsupported buyer reply classification")
        states.add(state)
    conflict = (
        "BUYER_ONBOARDING_PAUSED" in states
        and any(s in states for s in (
            "BUYER_REVIEW_OPEN",
            "BUYER_PILOT_TERMS_PROPOSED",
            "BUYER_DIRECT_ROUTE_TESTED_CLAIM",
        ))
    )
    if conflict:
        posture = "CONFLICTING_BUYER_ONBOARDING_HOLD"
        next_action = "RECONCILE_CONTRADICTORY_BUYER_RESPONSES_NO_ACTIVATION"
    elif "BUYER_ONBOARDING_PAUSED" in states:
        posture = "BUYER_ONBOARDING_PAUSED_HOLD"
        next_action = "WAIT_BUYER_CONFIRMED_REOPEN_DATE"
    elif "BUYER_DIRECT_ROUTE_TESTED_CLAIM" in states:
        posture = "DIRECT_BUYER_ROUTE_CLAIM_ONLY"
        next_action = "COMPLETE_EXISTING_WEBSITE_LEGAL_TRACKING_FINANCE_GATES"
    elif "BUYER_PILOT_TERMS_PROPOSED" in states:
        posture = "BUYER_TERMS_OFFERED_NOT_ONBOARDED"
        next_action = "REVIEW_EXACT_PILOT_TERMS_SOURCE_AND_PAYOUT_WITH_FOUNDER"
    elif "BUYER_APPLICATION_REQUIRED" in states:
        posture = "APPLICATION_AND_SOURCE_REVIEW_NEEDED"
        next_action = "REVIEW_EXISTING_SOURCE_ELIGIBILITY_BEFORE_APPLICATION"
    else:
        posture = "BUYER_INTEREST_NOT_VERIFIED"
        next_action = "WAIT_AUTHENTIC_BUYER_COMMERCIAL_REPLY"

    blockers = ["ORIGINAL_MESSAGE_RECEIPT_CUSTODY_REQUIRED",
                "ORIGINAL_SUPPRESSION_AND_CONSENT_CHECK_REQUIRED",
                "INDEPENDENT_BUYER_TERMS_AND_SOURCE_RIGHTS_REVIEW_REQUIRED",
                "FINANCIAL_SETTLEMENT_UNVERIFIED"]
    if conflict:
        blockers.append("CONFLICTING_BUYER_ONBOARDING_STATEMENTS")
    if not row["candidate_source_exists"]:
        blockers.append("OWNED_COMPLIANT_SOURCE_NOT_READY")
    if not row["independently_verified_qualified_demand"]:
        blockers.append("GENUINE_QUALIFIED_ENQUIRIES_UNVERIFIED")
    if proposed is None:
        blockers.append("BUYER_SPECIFIC_PAYOUT_AMOUNT_NOT_DEFINED")
    # A caller's "source exists" or "demand verified" flags are not an
    # owner-authenticated canonical receipt. Their truth is NOT asserted.
    blockers.append("AUTHENTICATED_CANONICAL_SOURCE_AND_BUYER_JOIN_NOT_ESTABLISHED")
    return {
        "buyer_key": key, "market": market, "vertical": vertical,
        "programme": programme,
        "reviewed_message_ref_count": len(seen),
        "message_claims_provided_not_independently_verified": True,
        "reported_terms_posture": posture,
        "next_owner": owner,
        "next_action": next_action,
        "proposed_payout_cents": proposed,
        "payout_currency": currency,
        "quoted_payout_is_settled_earnings": False,
        "source_eligibility_independently_verified": False,
        "genuine_enquiries_independently_verified": False,
        "partner_onboarded_and_approved": False,
        "tracking_and_payout_verified": False,
        "website_live_traffic_authorized": False,
        "buyer_sends_authorized": False,
        "accepted_calls_count": None,
        "settled_revenue_cents": None,
        "blockers": sorted(set(blockers)),
        "execution_authority": "none",
    }


def review_buyer_offer_portfolio(
    rows: Sequence[Mapping[str, Any]], *, as_of: datetime,
) -> dict[str, Any]:
    """Separate company-specific offer evidence; never join partner terms."""
    now = _time(as_of, "as_of")
    if type(rows) not in (list, tuple) or len(rows) > MAX_BUYERS:
        raise ValueError("bounded buyer set required")
    output = [review_buyer_offer(row, as_of=now) for row in rows]
    keys = [x["buyer_key"] for x in output]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate buyer programme")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "reviewed_buyers": output,
        "buyer_record_count": len(output),
        "buying_relationships_not_cross_licensed": True,
        "crm_mutations": False, "new_partner_onboarding": False,
        "new_first_party_traffic": False,
        "seller_payouts_processed": False,
        "verified_customer_enquiries": None,
        "verified_accepted_calls": None,
        "verified_settled_revenue_cents": None,
        "site_releases": False, "outbound_sent": False,
        "execution_authority": "none",
    }
