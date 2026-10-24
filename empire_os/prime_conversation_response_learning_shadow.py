"""Original PRIME Conversation OS outcome-feedback SHADOW, not model learning.

Only owner-prepared, privacy-minimal, pseudonymous observed outcome rows.
No private transcript, emotional/psychological scoring, user targeting,
causal uplift, model-weight update, CRM change or send authority.
An asserted source flag or fixture is NOT signed original provider proof.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
import re
from typing import Any, Mapping, Sequence

from empire_os.prime_conversation_objection_shadow import CUES

SCHEMA = "empire.prime.original_conversation_response_outcome_shadow.v1"
MIN_GROUP = 10
MAX_ROWS = 500
MAX_HORIZON = timedelta(days=30)
CASE_DIGEST = re.compile(r"^[a-f0-9]{64}$")
APPROACHES = frozenset({x[2] for x in CUES} | {
    "ACKNOWLEDGE_EXPRESSED_CONCERN_AND_ASK_WHAT_WOULD_HELP",
    "NO_NEW_REPLY_SUGGESTED_FROM_CUES",
})
OUTCOMES = frozenset({
    "QUESTION_ANSWERED_REPORTED",
    "FOLLOWUP_QUESTION_OBSERVED",
    "DECLINED_OBSERVED",
    "OPTOUT_OBSERVED",
    "UNKNOWN_PENDING",
})
FIELDS = frozenset({
    "case_digest", "approach_code",
    "original_inbound_at", "human_reply_at",
    "response_observed_at", "outcome_code",
    "original_owner_readback_reviewed", "permitted_purpose_reviewed",
    "synthetic", "transcript_or_personal_details_included",
})


def _when(value: Any) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise ValueError("original_observed_response_clock_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise ValueError("invalid_original_response_clock") from None
    if parsed.utcoffset() is None:
        raise ValueError("timezone_aware_original_response_clock_required")
    return parsed.astimezone(timezone.utc)


def _coarse(n: int) -> str | None:
    if n < MIN_GROUP:
        return None
    lo = (n // MIN_GROUP) * MIN_GROUP
    return f"{lo}-{lo + MIN_GROUP - 1}"


def review_objection_response_outcomes(
    *, original_owner_rows: Sequence[Mapping[str, Any]] | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Conservative, temporally ordered descriptive aggregates only.

    The true source authority remains the ORIGINAL owner signing/readback gate.
    Do not interpret correlations as effectiveness, customer mental state,
    predicted purchase probability, permission to follow up, or ROI.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware_source_outcome_review_clock_required")
    if original_owner_rows is not None and (
        type(original_owner_rows) not in (list, tuple)
        or len(original_owner_rows) > MAX_ROWS
    ):
        raise ValueError("bounded_original_outcome_feedback_required")
    now = as_of.astimezone(timezone.utc)
    seen: set[str] = set()
    all_counts: Counter[str] = Counter()
    observed_counts: Counter[tuple[str, str]] = Counter()
    pending = 0
    for row in original_owner_rows or ():
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError("exact_privacy_minimal_outcome_row_required")
        digest = row["case_digest"]
        if type(digest) is not str or CASE_DIGEST.fullmatch(digest) is None:
            raise ValueError("purpose_scoped_opaque_case_digest_required")
        if digest in seen:
            raise ValueError("original_outcome_case_replay_or_duplicate")
        seen.add(digest)
        approach = row["approach_code"]
        outcome = row["outcome_code"]
        if type(approach) is not str or approach not in APPROACHES:
            raise ValueError("unrecognised_human_reply_approach")
        if type(outcome) is not str or outcome not in OUTCOMES:
            raise ValueError("unknown_original_observed_outcome")
        if (row["original_owner_readback_reviewed"] is not True
            or row["permitted_purpose_reviewed"] is not True
            or row["synthetic"] is not False
            or row["transcript_or_personal_details_included"] is not False):
            raise ValueError("original_owner_outcome_source_hold")
        inbound = _when(row["original_inbound_at"])
        human = _when(row["human_reply_at"]) if row["human_reply_at"] is not None else None
        actual = (_when(row["response_observed_at"])
                  if row["response_observed_at"] is not None else None)
        # A no-reply policy is never treated as a sent response.
        if approach == "NO_NEW_REPLY_SUGGESTED_FROM_CUES" and human is not None:
            raise ValueError("no_reply_policy_cannot_claim_a_sent_reply")
        if (approach == "NO_NEW_REPLY_SUGGESTED_FROM_CUES"
            and outcome not in ("UNKNOWN_PENDING", "DECLINED_OBSERVED", "OPTOUT_OBSERVED")):
            raise ValueError("no_reply_policy_cannot_claim_question_answered")
        if human is None and approach != "NO_NEW_REPLY_SUGGESTED_FROM_CUES":
            raise ValueError("human_sent_response_proof_missing")
        if (human is not None and not inbound <= human <= now
            or inbound > now + timedelta(minutes=5)):
            raise ValueError("noncausal_original_reply_timing")
        if actual is not None and (
            actual < (human or inbound)
            or actual > now + timedelta(minutes=5)
            or actual - (human or inbound) > MAX_HORIZON
        ):
            raise ValueError("noncausal_original_outcome_timing")
        if (outcome == "UNKNOWN_PENDING" and actual is not None
            or outcome != "UNKNOWN_PENDING" and actual is None):
            raise ValueError("censored_vs_observed_outcome_conflict")
        all_counts[approach] += 1
        if outcome == "UNKNOWN_PENDING":
            pending += 1
        else:
            observed_counts[(approach, outcome)] += 1
    result_groups = []
    for approach in sorted(all_counts):
        n = all_counts[approach]
        if n < MIN_GROUP:
            continue
        result_groups.append({
            "approach_code": approach,
            "case_count_band": _coarse(n),
            "observed_outcome_code_count_bands": {
                outcome: _coarse(observed_counts[(approach, outcome)])
                for outcome in sorted(OUTCOMES - {"UNKNOWN_PENDING"})
                if observed_counts[(approach, outcome)] >= MIN_GROUP
            },
            "descriptive_only_not_causal_lift": True,
            "independent_provider_receipts_not_verified_by_this_module": True,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": (
            "NO_ORIGINAL_OUTCOME_ROWS_CONNECTED"
            if original_owner_rows is None else
            "OUTCOME_AGGREGATION_HELD_SMALL_COHORT"
            if not result_groups else
            "UNAUTHENTICATED_OWNER_REVIEWED_DESCRIPTIVE_COHORT_ONLY"
        ),
        "eligible_case_count_band_if_at_least_ten": _coarse(len(seen)),
        "unresolved_censored_case_count_band_if_at_least_ten": _coarse(pending),
        "approach_groups_sufficient_for_coarse_review": result_groups,
        "small_cohort_categories_suppressed": True,
        "individual_emotions_personality_or_risk_scores_recorded": False,
        "person_level_prediction_or_profiling": False,
        "treatment_effect_or_uplift_established": False,
        "learned_weights_promoted": False,
        "independent_original_source_provenance_verified": False,
        "original_empiredb_replay_guard_verified": False,
        "verified_buyer_conversion_count": None,
        "realized_revenue_cents": None,
        "send_authorized": False,
        "crm_writes": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
