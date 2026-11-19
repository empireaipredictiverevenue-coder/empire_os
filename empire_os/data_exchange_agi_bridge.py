"""AGI-style Data Exchange reasoning bridge over existing governed components.

This is an OBSERVE-only cognitive research specialist, NOT human-level AGI.
It reuses existing Empire AGI orchestration, memory routing, policy review,
source history, predictive verification and cognitive planning contracts.
No new daemon, model, database, timer, contact, customer export or payment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from empire_os.agi_capabilities import review_capability_request
from empire_os.agi_control_plane import build_cognitive_packet
from empire_os.agi_orchestrator import build_agi_orchestration_packet
from empire_os.data_exchange_history import build_construction_history
from empire_os.data_exchange_predictive_review import (
    review_construction_prediction_cohort,
)
from empire_os.data_exchange_procurement_context import (
    SCHEMA as PROCUREMENT_SCHEMA,
    NOTICE, OCID, TAGS, _date as procurement_timestamp,
)

SCHEMA = "empire.data_exchange.agi_research_bridge.v1"
PRODUCT = "empire_construction_signals"
TASK = "data-exchange:construction:evidence-review"
NO_EXECUTE = (
    "No outbound or private contacts",
    "No inferred project/entity joins without direct proof",
    "No customer data licensing absent rights review",
    "No forecast accuracy claim without independent holdout",
    "No production writes, payments or model promotion",
)


def _check_procurement(value: Any, *, now: datetime) -> dict[str, Any] | None:
    """Accept strictly shaped previous source projection, not raw private data."""
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "mode", "source_id", "source_dataset",
        "window_from", "window_to", "requested_limit", "sample_count",
        "notices", "source_rights_status", "cross_source_entity_link",
        "relationship_to_construction_records", "source_claim_verification",
        "buyer_intent_verified", "customer_delivery_enabled",
        "data_resale_authorized", "outbound_enabled", "payment_execution",
        "production_writes", "actual_revenue", "execution_authority",
    }:
        raise ValueError("procurement source projection shape is untrusted")
    if (
        value["schema_version"] != PROCUREMENT_SCHEMA
        or value["mode"] != "OBSERVE"
        or value["source_id"] != "gb_find_a_tender_ocds"
        or value["source_dataset"] != "find-a-tender-ocds-releases"
        or value["source_rights_status"]
           != "DATASET_LICENSE_STATED_FIELD_REVIEW_PENDING"
        or value["cross_source_entity_link"] != "NOT_VERIFIED"
        or value["relationship_to_construction_records"] != "NOT_ESTABLISHED"
        or value["source_claim_verification"]
           != "OFFICIAL_API_NOT_INDEPENDENTLY_REVIEWED"
        or value["buyer_intent_verified"] is not False
        or value["execution_authority"] != "NONE"
        or any(value[k] is not False for k in (
            "customer_delivery_enabled", "data_resale_authorized",
            "outbound_enabled", "payment_execution", "production_writes",
            "actual_revenue",
        ))
    ):
        raise ValueError("procurement authority or source rights mismatch")
    notices = value["notices"]
    count = value["sample_count"]
    if (
        not isinstance(notices, list)
        or not isinstance(count, int) or isinstance(count, bool)
        or not 1 <= count <= 5 or len(notices) != count
    ):
        raise ValueError("procurement sample invalid")
    ids = set()
    for item in notices:
        if not isinstance(item, Mapping) or set(item) != {
            "source_id", "release_id", "ocid", "source_url",
            "release_date", "stages", "relation_to_brownfield_site",
            "buyer_intent_from_site",
        }:
            raise ValueError("unreviewed procurement fields")
        if (
            item["source_id"] != "gb_find_a_tender_ocds"
            or item["relation_to_brownfield_site"] != "NONE_VERIFIED"
            or item["buyer_intent_from_site"] != "UNKNOWN"
            or not isinstance(item["release_id"], str)
            or not NOTICE.fullmatch(item["release_id"])
            or not isinstance(item["ocid"], str)
            or not OCID.fullmatch(item["ocid"])
            or not isinstance(item["stages"], list)
            or not item["stages"]
            or any(stage not in TAGS for stage in item["stages"])
            or not item["source_url"] ==
                "https://www.find-tender.service.gov.uk/Notice/" + item["release_id"]
            or procurement_timestamp(item["release_date"]) > now
            or item["release_id"] in ids
        ):
            raise ValueError("procurement identity and linkage invalid")
        ids.add(item["release_id"])
    return {"count": count, "release_ids": sorted(ids)}


def review_data_exchange_agi(
    *,
    source_snapshots: Sequence[Mapping[str, Any]],
    tenant_id: str,
    assessed_at: datetime,
    procurement: Mapping[str, Any] | None = None,
    prediction_pairs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Produce a hypothesis/critic/verification agenda from validated evidence."""
    if (
        not isinstance(tenant_id, str) or not tenant_id.strip()
        or assessed_at.tzinfo is None or assessed_at.utcoffset() is None
    ):
        raise ValueError("scoped tenant and timezone-aware assessment required")
    now = assessed_at.astimezone(timezone.utc)
    history = build_construction_history(source_snapshots, assessed_at=now)
    forecast = review_construction_prediction_cohort(
        source_snapshots=source_snapshots, pairs=prediction_pairs,
        tenant_id=tenant_id, assessed_at=now,
    )
    procurement_view = _check_procurement(procurement, now=now)
    # The evidence dossier already imports this bridge's procurement
    # validator. Resolve the assembled read model only at call time to
    # avoid a module-load cycle, without duplicating source validation.
    from empire_os.data_exchange_signal_board import build_signal_board
    signal_board = build_signal_board(
        source_snapshots=source_snapshots,
        procurement=procurement,
        assessed_at=now,
        limit=8,
    )
    if (
        signal_board["source_history_sha256"] != history["latest_chain_sha256"]
        or signal_board["customer_delivery_enabled"] is not False
        or signal_board["data_resale_authorized"] is not False
    ):
        raise ValueError("signal review source lineage mismatch")
    if history["execution_authority"] != "NONE":
        raise ValueError("history contains execution authority")

    history_ref = "empire:construction_history:" + history["latest_chain_sha256"]
    evidence = [history_ref]
    if procurement_view:
        evidence.extend(
            "find-a-tender:notice:" + value
            for value in procurement_view["release_ids"]
        )

    # This is a falsifiable research agenda, not generated buyer intent.
    hypotheses = [
        {
            "key": "stage_change_precedes_opportunity",
            "claim": "A verified planning status change may precede a later commercial event",
            "state": "UNTESTED",
            "alternatives": [
                "The site may never proceed",
                "Registry updates may lag project activity",
                "A contractor may already have been appointed",
            ],
            "required_disconfirmation": (
                "Timestamped independent outcomes and a no-change baseline"
            ),
        },
        {
            "key": "procurement_corroborates_project",
            "claim": "An independently identified procurement may corroborate a site",
            "state": "UNTESTED",
            "alternatives": [
                "Both events may be unrelated despite shared geography",
                "Tender publication is not evidence of site identity",
            ],
            "required_disconfirmation": (
                "Official common project identifier or direct document citation"
            ),
        },
    ]
    gaps = ["DATASET_AND_FIELD_RIGHTS_REVIEW_REQUIRED"]
    if history["observed_change_count"] == 0:
        gaps.append("NO_GENUINE_SOURCE_FIELD_TRANSITIONS")
    if history["held_window_count"]:
        gaps.append("SOURCE_HISTORY_HAS_UNCOMPARABLE_WINDOWS")
    if procurement_view is None:
        gaps.append("INDEPENDENT_PROCUREMENT_CONTEXT_MISSING")
    else:
        gaps.append("CROSS_SOURCE_PROJECT_LINK_NOT_VERIFIED")
    if forecast["review_status"] == "HOLD":
        gaps.extend(forecast["blockers"])
    gaps.append("INDEPENDENT_TIME_SPLIT_HOLDOUT_NOT_VERIFIED")
    gaps.append("PAID_BUYER_DEMAND_NOT_VERIFIED")
    gaps = sorted(set(gaps))

    source_action = (
        ("capture_later_observations", "Capture comparable later government observations", 90)
        if not history["observed_change_count"] else
        ("independently_verify_source_transitions", "Verify each observed change against official source history", 90)
    )
    procurement_action = (
        ("collect_independent_procurement_context", "Collect bounded official procurement evidence", 80)
        if procurement_view is None else
        ("verify_cross_source_project_identity", "Check direct official project identifiers before joins", 80)
    )
    forecast_action = (
        ("validate_commercial_outcomes", "Review genuine forecast/outcome evidence and time-split holdout", 70)
        if forecast["review_status"] == "HOLD" else
        ("test_independent_holdout", "Compare the model against time-split reference baselines", 70)
    )
    tasks = [
        ("review_dataset_rights", "Review source rights, attribution, personal-data exclusions", 100),
        source_action,
        procurement_action,
        forecast_action,
        ("research_first_paid_buyer", "Prepare email-first buyer validation for founder approval", 60),
    ]
    candidates = [
        {
            "option_id": name, "summary": summary,
            "expected_value_cents": None, "expected_cost_cents": None,
            "risk_score": None, "reversible": True,
            "required_authority": "OBSERVE", "evidence_refs": evidence,
        }
        for name, summary, _ in tasks
    ]
    # Existing AGI capability policy explicitly gates evidence.read.
    policy = review_capability_request({
        "capability": "evidence.read",
        "agent_id": "empire-data-exchange-agi-reviewer",
        "authority_mode": "OBSERVE",
        "approval_present": False,
        "granted_capabilities": ["evidence.read"],
    })
    if policy["permitted"] is not True or policy["execution_performed"] is not False:
        raise ValueError("AGI evidence capability not available")
    cognitive = build_cognitive_packet(
        task_id=TASK, goal="Validate a commercially valuable, lawful construction feed",
        world_state_ref=history_ref,
        evidence_refs=evidence,
        options=candidates, selected_option_id="review_dataset_rights",
        constraints=NO_EXECUTE,
        verifier={
            "status": "not_run", "evidence_supported": False,
            "policy_consistent": True, "freshness_verified": False,
            "independent": False, "issues": gaps,
        },
        policy={
            "status": "passed", "capability": "evidence.read",
            "allowed": True, "approval_required": False,
            "approval_present": False, "blockers": [],
        },
        authority_mode="OBSERVE", side_effect_class="none",
    )
    orchestration = build_agi_orchestration_packet(
        task_id=TASK,
        goal="Coordinate construction evidence research without commercial authority",
        world_state_ref=history_ref, evidence_refs=evidence,
        predictive_revenue={
            "status": "UNAVAILABLE", "missing_fields": forecast["blockers"]
                or ["independent_holdout_and_causation_review"],
        },
        predictive_cloud={
            "status": "UNAVAILABLE", "missing_fields":
                ["validated_cross_source_project_identity"],
        },
        future_trend={
            "status": "UNAVAILABLE", "missing_fields":
                ["time_ordered_outcomes_and_negative_controls"],
        },
        topic_keys=("construction", "source_rights", "predictive_revenue"),
    )
    if (
        cognitive["execution_ready"]
        or orchestration["execution_ready"]
        or orchestration["human_level_agi_claimed"]
    ):
        raise ValueError("AGI bridge must remain advisory and non-executing")

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "architecture": "existing_empire_agi_specialist_bridge",
        "human_level_agi_claimed": False,
        "model_inference_performed": False,
        "model_dependency_required": False,
        "product": PRODUCT,
        "evidence_refs": evidence,
        "source_change_count": history["observed_change_count"],
        "history_held_windows": history["held_window_count"],
        "signal_board_status": signal_board["feed_status"],
        "signal_board_rights_status": signal_board["rights_clearance"],
        "signal_board_source_evidence_sha256": signal_board["source_evidence_sha256"],
        "signal_review_queue": [
            {
                "event_id": item["event_id"],
                "record_id": item["source_record_id"],
                "review_action": item["review_action"],
                "latest_snapshot_status": item["latest_snapshot_status"],
                "execution_ready": False,
            }
            for item in signal_board["review_queue"]
        ],
        "procurement_context_count": (
            procurement_view["count"] if procurement_view else 0
        ),
        "forecast_evaluation_status": forecast["review_status"],
        "hypotheses": hypotheses,
        "unresolved_evidence": gaps,
        "recommended_workstream": candidates[0]["option_id"],
        "research_workstreams": [
            {"workstream": n, "summary": s, "priority": priority}
            for n, s, priority in tasks
        ],
        "existing_agi_orchestration": orchestration,
        "existing_agi_cognitive_packet": cognitive,
        "existing_capability_review": policy,
        "memory_retrieval_only": orchestration["memory_query"]["retrieval_only"],
        "independent_verifier_completed": False,
        "predictive_marketing_claim_ready": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "model_mutation": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
