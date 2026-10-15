"""Scientific evidence review of the EXISTING canonical V15/V16 custody.

No new agent, model, database, timer or commercial authority. Proves only
claims directly testable from stored, fully verified source observations.
If the 16-row read window lacks the original genesis, independent origin
review is held; never treat a rolling-window digest as the full chain.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_change_intelligence import _validated_preview
from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, parse_at, verify_custody_window,
)
from empire_os.data_exchange_temporal_quality import (
    PILOT_IDS, build_temporal_quality,
)

SCHEMA = "empire.data_exchange.canonical_scientific_review.v17"
CHANGE_FIELDS = ("planning_permission_status", "site_area_hectares")
FIXED_ACTIONS = (
    "INDEPENDENT_FIELD_RIGHTS_REVIEW",
    "SOURCE_REVISION_HISTORY_CORROBORATION",
    "INDEPENDENT_PROJECT_IDENTITY_EVIDENCE",
    "TIME_SPLIT_NEGATIVE_CONTROLS",
    "REAL_OUTCOME_COHORT_AND_BUYER_VALIDATION",
)


def build_scientific_custody_review(
    rows: Sequence[Mapping[str, Any]], *,
    assessed_at: datetime,
    recheck: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe evidence strength and falsification tasks without predictions.

    Reuses V15 canonical hash verification, V16 quality controls and, when
    eligible, the pre-existing read-only Data Exchange AGI research bridge.
    """
    if (
        not isinstance(assessed_at, datetime)
        or assessed_at.tzinfo is None or assessed_at.utcoffset() is None
    ):
        raise CustodyIntegrityError("scientific review needs aware time")
    now=assessed_at.astimezone(timezone.utc)
    proof=verify_custody_window(rows)
    quality=build_temporal_quality(rows,assessed_at=now,recheck=recheck)
    if (
        quality["canonical_head_sha256"]!=proof["head_chain_sha256"]
        or quality["customer_delivery_enabled"] is not False
        or quality["production_writes"] is not False
    ):
        raise CustodyIntegrityError("scientific and custody proof mismatch")
    latest=rows[-1]
    latest_at=parse_at(latest["source_observed_at"])
    current=_validated_preview(latest["snapshot_json"],latest_at)
    if set(current) - PILOT_IDS:
        raise CustodyIntegrityError("unreviewed scientific record scope")
    latest_ids=set(current)
    matched: list[str]=[]
    changed: list[str]=[]
    stable: list[str]=[]
    absent: list[str]=[]
    if len(rows)>1:
        previous=rows[-2]
        earlier_at=parse_at(previous["source_observed_at"])
        old=_validated_preview(previous["snapshot_json"],earlier_at)
        matched=sorted(set(old)&latest_ids)
        changed=[ident for ident in matched if any(
            old[ident][key]!=current[ident][key] for key in CHANGE_FIELDS
        )]
        stable=sorted(set(matched)-set(changed))
        absent=sorted(set(old)^latest_ids)
        # This is a descriptive comparison of the latest TWO samples only.
        # It cannot prove sites have opened/closed or activity increased.
        if len(changed)+len(stable)!=len(matched):
            raise CustodyIntegrityError("matched pilot cohort accounting mismatch")

    has_two=len(rows)>=2
    origin_verified=proof["window_origin_anchored_to_genesis"]
    temporal_eligible=(
        has_two and origin_verified and quality["minimum_24h_separation_met"]
        and quality["held_comparison_count"]==0
        and quality["status"]=="INTERNAL_REVIEW_READY"
    )
    agi_review_status="NOT_RUN_REQUIRES_TWO_GENUINE_OBSERVATIONS"
    agi_tasks: list[dict[str, Any]]=[]
    agi_unresolved: list[str]=[]
    agi_ref: str|None=None
    if (has_two and origin_verified
        and quality["minimum_24h_separation_met"]
        and quality["held_comparison_count"]==0
        and quality["latest_observation_age_seconds"]<=72*3600):
        # Existing specialist only; no model inference, tool use or external
        # action. Use real DB snapshots, never generated historical fixtures.
        from empire_os.data_exchange_agi_bridge import review_data_exchange_agi
        packet=review_data_exchange_agi(
            source_snapshots=[r["snapshot_json"] for r in rows],
            tenant_id="empire-internal-construction-observe",
            assessed_at=now, procurement=None, prediction_pairs=(),
        )
        if (
            packet["model_inference_performed"] is not False
            or packet["human_level_agi_claimed"] is not False
            or packet["source_change_count"]!=quality["observed_source_field_changes"]
            or packet["signal_board_status"]!=quality["v14_board_status"]
            or packet["customer_delivery_enabled"] is not False
            or packet["existing_agi_orchestration"]["execution_ready"] is not False
            or packet["existing_agi_cognitive_packet"]["execution_ready"] is not False
        ):
            raise CustodyIntegrityError("AGI advisory evidence exceeds canonical authority")
        if "empire:construction_history:" + proof["head_chain_sha256"] not in packet["evidence_refs"]:
            raise CustodyIntegrityError("AGI review history does not match persisted custody")
        agi_tasks=[
            {"workstream":task["workstream"],"priority":task["priority"]}
            for task in packet["research_workstreams"]
        ]
        agi_unresolved=sorted(packet["unresolved_evidence"])
        agi_ref="empire:construction_history:"+proof["head_chain_sha256"]
        agi_review_status="EXISTING_AGI_EVIDENCE_REVIEW_OBSERVE_ONLY"
    elif has_two and not origin_verified:
        agi_review_status="HOLD_ROLLING_WINDOW_ORIGIN_NOT_REVALIDATED"
    elif has_two:
        agi_review_status="HOLD_TEMPORAL_EVIDENCE_NOT_READY_FOR_AGI"

    blockers=list(quality["holds"])
    if not origin_verified:
        blockers.append("GENESIS_OUTSIDE_VERIFIED_READ_WINDOW")
    if not temporal_eligible:
        blockers.append("NOT_ENOUGH_VERIFIED_TEMPORAL_EVIDENCE")
    if not changed:
        blockers.append("NO_OBSERVED_MONITORED_FIELD_TRANSITIONS_IN_LATEST_PAIR")
    blockers.extend([
        "SOURCE_AUTHENTICITY_NOT_INDEPENDENTLY_ATTESTED",
        "SOURCE_FIELD_RIGHTS_NOT_INDEPENDENTLY_CLEARED",
        "NO_GROUNDED_CAUSAL_COMPARISON",
        "NO_VERIFIED_BUYER_DEMAND_OR_COMMERCIAL_OUTCOMES",
    ])
    blockers=sorted(set(blockers))
    conclusions={
        "local_custody_integrity":"VERIFIED_LOCAL_SHA256_LINKS",
        "government_attestation":"NOT_VERIFIED",
        "repeat_source_corroboration":quality["same_source_recheck"],
        "historical_sample_comparison":(
            "INTERNAL_DESCRIPTIVE_ONLY" if temporal_eligible
            else "INSUFFICIENT_OR_HELD"
        ),
        "site_lifecycle_causality":"NOT_ESTABLISHED",
        "commercial_buyer_intent":"NOT_VERIFIED",
        "predictive_accuracy":"NOT_VERIFIED",
    }
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":(
            "INTERNAL_FALSIFIABLE_REVIEW_ONLY"
            if temporal_eligible and changed
            else "HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
        ),
        "canonical_observation_count_in_window":len(rows),
        "canonical_head_sequence":proof["last_sequence"],
        "canonical_head_sha256":proof["head_chain_sha256"],
        "genesis_verified_in_window":origin_verified,
        "external_anchor_verified":False,
        "pilot_universe_exact_ids":sorted(PILOT_IDS),
        "pilot_record_count_latest":len(latest_ids),
        "latest_pair_matched_entity_count":len(matched),
        "latest_pair_changed_entity_count":len(changed),
        "latest_pair_unchanged_control_entity_count":len(stable),
        "latest_pair_membership_mismatch_count":len(absent),
        "changed_entity_ids_latest_pair":changed,
        "unchanged_entity_ids_latest_pair":stable,
        "coverage_claim":"THREE_SELECTED_SOURCE_ENTITIES_ONLY",
        "regional_market_universe_verified":False,
        "current_source_recheck":quality["same_source_recheck"],
        "temporal_quality_status":quality["status"],
        "v14_board_status":quality["v14_board_status"],
        "v14_observed_field_changes_in_window":quality["observed_source_field_changes"],
        "existing_agi_review_status":agi_review_status,
        "existing_agi_evidence_ref":agi_ref,
        "existing_agi_research_workstreams":agi_tasks,
        "existing_agi_unresolved_evidence":agi_unresolved,
        "hypotheses_verified":False,
        "claims":conclusions,
        "scientific_blockers":blockers,
        "manual_validation_actions":list(FIXED_ACTIONS),
        "model_inference_performed":False,
        "independent_field_rights_review_completed":False,
        "buyer_intent_verified":False,
        "forecast_accuracy_verified":False,
        "commercial_revenue_verified":False,
        "customer_delivery_enabled":False,
        "data_resale_authorized":False,
        "outbound_enabled":False,
        "payment_execution":False,
        "production_writes":False,
        "execution_authority":"NONE",
    }
