"""Passive adaptive-commercial observer for the EXISTING EmpireOS Ops cycle.

All evidence reads are original-owner bounded source files. Existing Ops Control
owns the cadence and its atomic latest.json; this adapter has NO persistence,
new scheduler, customer action, worker dispatch or model mutation authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from empire_os.commercial_sales_director_adaptive_review import SOURCE_KINDS
from empire_os.commercial_adaptive_checkpoint_guard import recover_safe_adaptive_checkpoints
from empire_os.conversation_control_operational_truth import SOURCE_PATHS
from scripts.review_commercial_adaptive_intelligence_20261020 import (
    build_adaptive_commercial_runtime,
)

SCHEMA = "empire.ops_control.adaptive_commercial_bridge.v1"
MAX_SOURCE_SIZE = 3_000_000
SOURCE_FILES = {
    "conversation_recovery": "runtime/conversation_recovery/latest.json",
    "commercial_catalog": "runtime/commercial_catalog/latest.json",
    "revenue_distribution": "runtime/revenue_distribution/latest.json",
    "promotion_research": "runtime/buyer_acquisition/promotion_plan_latest.json",
    "conversation_control_collector": SOURCE_PATHS["collector"],
    "conversation_control_linkage": SOURCE_PATHS["linkage"],
    "conversation_control_health": SOURCE_PATHS["health"],
    "founder_mailbox_observer": SOURCE_PATHS["mailbox_observer"],
    "identity_discovery": SOURCE_PATHS["identity_discovery"],
    "identity_gap": SOURCE_PATHS["identity_gap"],
}
assert set(SOURCE_FILES) == SOURCE_KINDS


def source_receipts(root: Path) -> dict[str, str]:
    """Content-change fingerprints, NOT a claim of source authenticity."""
    result = {}
    for name, relative in sorted(SOURCE_FILES.items()):
        path = root / relative
        try:
            if (path.is_symlink() or not path.is_file()
                    or path.stat().st_size > MAX_SOURCE_SIZE):
                raise OSError("source unavailable")
            payload = path.read_bytes()
            if len(payload) > MAX_SOURCE_SIZE:
                raise OSError("source over limit")
        except OSError:
            payload = ("UNAVAILABLE_OR_UNTRUSTED:" + name).encode("ascii")
        result[name] = sha256(payload).hexdigest()
    return result


def observe_ops_adaptive_commercial(
    *,
    root: Path,
    previous_ops_snapshot: Mapping[str, Any] | None,
    conversation_proof: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Existing Ops cycle can store the two checkpoints in its snapshot.

    A bad/missing source returns a SAFE unavailable state, not a false green.
    Never include raw exceptions or source field values in output.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware Ops observation required")
    prior = previous_ops_snapshot or {}
    if not isinstance(prior, Mapping):
        prior = {}
    previous_sales = prior.get("adaptive_sales_review")
    previous_control = prior.get("adaptive_commercial_review")
    prior_summary = prior.get("adaptive_commercial_summary")
    try:
        result = build_adaptive_commercial_runtime(
            root, now=now.astimezone(timezone.utc),
            previous_sales=previous_sales,
            previous_control=previous_control,
            conversation_proof=dict(conversation_proof),
            owner_source_receipts=source_receipts(root),
            include_sales_review=True,
        )
        sales = result["sales"]
        control = result["control"]
        material_change = control["transition"] != "UNCHANGED_COMMERCIAL_HOLD"
        source_changed = bool(sales["changed_owner_source_names"]) and previous_sales is not None
        status = {
            "schema_version": SCHEMA,
            "status": "COMMERCIAL_EVIDENCE_REVIEW_HOLD",
            "available": True,
            "plain_language_reason": control["plain_language_reason"],
            "reviewed_at": now.astimezone(timezone.utc).isoformat(),
            "active_dependency_gates": len(control["active_dependency_gates"]),
            "parallel_owner_reviews_possible_not_dispatched": len(
                control["recommended_parallel_reviews_not_dispatched"]
            ),
            "persistent_hold_count": len(control["persistent_holds_three_or_more_observations"]),
            "recurring_gate_count": len(control["recurrent_evidence_gates"]),
            "material_evidence_changed": material_change,
            "original_source_changed_without_proof": (
                source_changed and not material_change
            ),
            "source_receipt_names_changed": list(sales["changed_owner_source_names"]),
            "operator_attention_due": control["operator_attention_due"],
            "repeated_work_suppressed": not material_change,
            "execution_authority": "none",
            "outbound_authorized": False,
            "agent_tasks_created": False,
        }
        # Stable identity for at-least-once retry after a crash between
        # change journal append and the existing latest.json replacement.
        receipt_set_digest = sha256(json.dumps(
            sales["owner_source_receipts"], sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        event_id = sha256((
            control["decision_signature"] + ":" +
            receipt_set_digest + ":" +
            ("MATERIAL" if material_change else "SOURCE_ONLY")
        ).encode("ascii")).hexdigest()
        change_event = (
            {
                "event_id": event_id,
                "owner_receipt_set_digest": receipt_set_digest,
                "observed_at": status["reviewed_at"],
                "event_code": (
                    "COMMERCIAL_EVIDENCE_STATE_CHANGED"
                    if material_change else "ORIGINAL_SOURCE_RECEIPT_CHANGED_ONLY"
                ),
                "decision_signature": control["decision_signature"],
                "changed_gate_names": list(control["changed_gate_names"]),
                "gates_newly_blocking": list(control["gates_newly_blocking"]),
                "gates_no_longer_reported": list(control["gates_no_longer_reported"]),
                "changed_owner_source_names": list(sales["changed_owner_source_names"]),
                "owner_dispatch_executed": False,
                "outbound_sent": False,
                "execution_authority": "none",
            } if material_change or source_changed else None
        )
        return {
            "summary": status,
            "sales": sales,
            "control": control,
            "change_event": change_event,
        }
    except Exception:
        # Never expose provider payloads, paths or raw exception values.
        # Only a validated minimal prior decision may survive an unavailable
        # source. Untrusted/unknown fields in a persisted Ops snapshot are
        # NEVER copied into the new current Founder-visible snapshot.
        retained_sales, retained_control = recover_safe_adaptive_checkpoints(
            previous_sales, previous_control,
        )
        return {
            "summary": {
                "schema_version": SCHEMA,
                "status": "ADAPTIVE_COMMERCIAL_EVIDENCE_UNAVAILABLE",
                "available": False,
                "plain_language_reason": (
                    "Existing commercial source contracts or prior decision memory "
                    "could not be verified. Keep all actions held and review with source owners."
                ),
                "reviewed_at": now.astimezone(timezone.utc).isoformat(),
                "operator_attention_due": False,
                "execution_authority": "none",
                "outbound_authorized": False,
                "agent_tasks_created": False,
            },
            # Keep existing trusted-looking packet only as a previous checkpoint
            # for re-evaluation; do not announce it as current readiness.
            "sales": retained_sales,
            "control": retained_control,
            "change_event": None,
        }
