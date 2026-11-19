"""Evidence-first, internal Construction Signal Board.

Integrates existing validated history, dossier and OGL field-rights preflight.
Never infers planning approval date, site creation, procurement linkage,
commercial buyer interest, probability, rights release or delivery authority.
No new scanner, data store, agents, transport or prediction implementation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_history import build_construction_history
from empire_os.data_exchange_rights_preflight import build_rights_preflight
from empire_os.data_exchange_change_intelligence import _validated_preview

SCHEMA = "empire.data_exchange.signal_board.v14"
MAX_QUEUE = 64
ALLOWED_FIELDS = frozenset({"planning_permission_status", "site_area_hectares"})
PRIORITIES = {"REVIEW", "CONTEXT"}


def _read_observation_time(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("untrusted event observation timestamp") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("naive source observation timestamp")
    return dt.astimezone(timezone.utc)


def _field_state(changes: Mapping[str, Any], latest: Mapping[str, Any] | None) -> str:
    if latest is None:
        return "NO_LATEST_SAMPLE_NOT_PROOF_OF_REMOVAL"
    agrees = [latest.get(key) == values["current"] for key, values in changes.items()]
    if all(agrees):
        return "STILL_REFLECTED_IN_LATEST_SAMPLE"
    if not any(agrees):
        return "SUPERSEDED_BY_LATER_OBSERVATION"
    return "PARTIALLY_SUPERSEDED_BY_LATER_OBSERVATION"


def build_signal_board(
    *,
    source_snapshots: Sequence[Mapping[str, Any]],
    procurement: Mapping[str, Any] | None,
    assessed_at: datetime,
    limit: int = 24,
) -> dict[str, Any]:
    """Produce a reproducible internal queue only from canonical validators.

    Caller-supplied flags, commercial assertions and external approval
    attestations have NO route to customer delivery. Latest change values
    are compared to the latest independently validated source snapshot.
    """
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("assessment requires timezone")
    if type(limit) is not int or not 1 <= limit <= MAX_QUEUE:
        raise ValueError("signal board limit out of bounds")
    now = assessed_at.astimezone(timezone.utc)

    # Both helpers REBUILD validation from raw observations. Never accept
    # a provided 'rights approved' or 'predictive result' JSON in lieu.
    history = build_construction_history(source_snapshots, assessed_at=now)
    rights = build_rights_preflight(
        source_snapshots=source_snapshots,
        procurement=procurement,
        assessed_at=now,
    )
    if (
        history.get("mode") != "OBSERVE"
        or history.get("customer_delivery_enabled") is not False
        or history.get("data_resale_authorized") is not False
        or rights.get("mode") != "OBSERVE"
        or rights.get("customer_delivery_enabled") is not False
        or rights.get("data_resale_authorized") is not False
        or rights.get("source_history_sha256") != history["latest_chain_sha256"]
        or rights.get("independent_field_rights_review") != "NOT_COMPLETED"
        or rights.get("source_licence_class") != "OPEN_GOVERNMENT_LICENCE_V3_STATED"
    ):
        raise ValueError("history or field-rights provenance inconsistent")

    latest_snapshot = source_snapshots[-1]
    # Validation at present time is already performed by rights preflight;
    # repeat it here to obtain a strict, unmodified current record index.
    latest = _validated_preview(latest_snapshot, now)
    event_index: set[str] = set()
    event_list: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []

    for window in history["comparison_windows"]:
        seq = window["to_sequence"]
        if window["assessment_status"] == "HOLD":
            held.append({
                "to_sequence": seq,
                "holds": list(window["holds"]),
                "source_change_promoted": False,
            })
            continue
        missing = list(window["not_in_later_sample"])
        new = list(window["newly_observed_in_sample"])
        if missing or new:
            coverage.append({
                "to_sequence": seq,
                "newly_sampled_ids": new,
                "no_longer_sampled_ids": missing,
                "meaning": "SAMPLE_MEMBERSHIP_CHANGE_NOT_SITE_LIFECYCLE",
                "new_project_claim": False,
                "removed_project_claim": False,
            })
        for event in window["observed_changes"]:
            if (
                not isinstance(event, Mapping)
                or event.get("event_id") in event_index
                or event.get("priority") not in PRIORITIES
                or event.get("buyer_intent_verified") is not False
                or event.get("commercial_outcome_verified") is not False
            ):
                raise ValueError("duplicate or promoted source event")
            changes = event.get("source_changes")
            if (
                not isinstance(changes, Mapping)
                or not changes
                or not set(changes).issubset(ALLOWED_FIELDS)
                or any(not isinstance(v, Mapping) or set(v) != {"previous", "current"}
                       or v["previous"] == v["current"] for v in changes.values())
            ):
                raise ValueError("unreviewed change fields")
            event_time = _read_observation_time(event["after_observed_at"])
            if event_time > now:
                raise ValueError("future source change event")
            event_index.add(event["event_id"])
            record = latest.get(event["record_id"])
            state = _field_state(changes, record)
            event_list.append({
                "event_id": event["event_id"],
                "source_record_id": event["record_id"],
                "source_url": event["source_url"],
                "before_observed_at": event["before_observed_at"],
                "after_observed_at": event["after_observed_at"],
                "days_since_empire_observation": (now - event_time).days,
                "observed_field_changes": {
                    k: {"previous": v["previous"], "current": v["current"]}
                    for k, v in sorted(changes.items())
                },
                "latest_snapshot_status": state,
                "review_priority": event["priority"],
                "review_action": (
                    "VERIFY_OFFICIAL_SOURCE_REVISION_AND_FIELD_RIGHTS"
                    if state == "STILL_REFLECTED_IN_LATEST_SAMPLE"
                    else "RECONCILE_SOURCE_OBSERVATION_HISTORY"
                ),
                "source_change_not_publication_time": True,
                "commercial_signal": False,
                "prediction_available": False,
                "customer_visible": False,
                "rights_released": False,
                "window_to_sequence": seq,
            })

    event_list.sort(key=lambda e: (
        0 if e["latest_snapshot_status"] == "STILL_REFLECTED_IN_LATEST_SAMPLE" else 1,
        0 if e["review_priority"] == "REVIEW" else 1,
        -_read_observation_time(e["after_observed_at"]).timestamp(),
        e["event_id"],
    ))
    queue = event_list[:limit]
    actionable = sum(e["latest_snapshot_status"] ==
                     "STILL_REFLECTED_IN_LATEST_SAMPLE" for e in queue)
    checked_rights = sorted({r["source_id"] for r in rights["rights_evidence"]})
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "product": "empire_construction_signals",
        "feed_status": (
            "HOLD_HISTORY_GAPS" if held
            else "OBSERVED_CHANGES_REVIEW_ONLY" if event_list
            else "NO_OBSERVED_FIELD_CHANGES"
        ),
        "as_of_utc": now.isoformat(),
        "source_history_sha256": history["latest_chain_sha256"],
        "source_evidence_sha256": rights["source_evidence_sha256"],
        "history_integrity": "LOCAL_HASH_CHAIN_UNANCHORED",
        "source_authenticity": "NOT_INDEPENDENTLY_VERIFIED",
        "source_datasets": checked_rights,
        "source_observation_count": history["snapshot_count"],
        "total_validated_changes": len(event_list),
        "queue_count": len(queue),
        "queue_truncated": len(event_list) > len(queue),
        "latest_reflected_in_queue": actionable,
        "review_queue": queue,
        "coverage_gap_count": len(coverage),
        "sample_coverage_changes": coverage,
        "held_comparison_count": len(held),
        "held_comparisons": held,
        "procurement_notices_in_sample": rights["procurement_notice_count"],
        "cross_source_project_join_verified": False,
        "field_lineage_review_required": True,
        "pending_field_review_count": len(rights["field_lineage"]),
        "rights_review_tasks": [r["control_id"] for r in rights["reviewer_checklist"]],
        "required_source_attributions": rights["rights_evidence"],
        "rights_clearance": "PENDING_INDEPENDENT_FIELD_REVIEW",
        "buyer_interest_verified": False,
        "forecast_accuracy_verified": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "actual_revenue": False,
        "execution_authority": "NONE",
    }
