"""Read-only original reply -> conversation -> intent linkage design.

Uses observed DB schema metadata only, never message content, person records,
secret DSNs, DB writes or inferred commercial approvals.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json

from empire_os.reply_lineage_health import assess_reply_lineage
from empire_os.conversation_reply_binding_review import review_identity_bindings

DISCOVERY = Path("runtime/control_plane/conversations_replies_binding_truth_latest.json")
GAP = Path("runtime/control_plane/conversations_replies_identity_gap_latest.json")
OUTPUT = Path("runtime/conversations_replies_control/reply_linkage_plan_latest.json")

REQUIRED = {
    "public.outbound_replies": (
        "intent_id", "provider_message_id", "normalized_from_contact",
        "received_at",
    ),
    "public.empire_conversations": (
        "id", "outbound_intent_id", "external_conversation_id",
    ),
    "public.outbound_intents": (
        "id", "prospect_id", "entity_id", "buyer_id", "opportunity_id",
    ),
}


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def plan(
    discovery: Mapping[str, Any],
    gap: Mapping[str, Any],
    *,
    now: datetime | None = None,
    market_gps: Mapping[str, Any] | None = None,
    controlled_identity_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("offset-aware time required")
    columns = {
        str(row.get("table")): {
            str(c.get("column"))
            for c in (row.get("columns") or []) if isinstance(c, Mapping)
        }
        for row in (discovery.get("database_candidates") or [])
        if isinstance(row, Mapping) and isinstance(row.get("table"), str)
    }
    missing = {
        table: sorted(set(fields).difference(columns.get(table, set())))
        for table, fields in REQUIRED.items()
    }
    complete_schema = all(not fields for fields in missing.values())
    gap_decision = (gap.get("decision") or {}).get("status")
    lineage_health = assess_reply_lineage(market_gps or {}, now)
    identity_review = (
        review_identity_bindings(controlled_identity_inputs)
        if controlled_identity_inputs is not None else None
    )
    trusted_join = False  # Schema evidence does NOT prove a data-level match.
    join_edges = [
        {
            "left": "public.outbound_replies.intent_id",
            "right": "public.outbound_intents.id",
            "join_cardinality_verified": trusted_join,
            "required_proof": "unique non-null original intent match for each reply",
        },
        {
            "left": "public.outbound_replies.intent_id",
            "right": "public.empire_conversations.outbound_intent_id",
            "join_cardinality_verified": trusted_join,
            "required_proof": (
                "exactly one active conversation per intent or direct provider "
                "thread evidence; reject zero and many-to-many matches"
            ),
        },
    ]
    blockers = []
    if not complete_schema:
        blockers.append("SCHEMA_COLUMNS_MISSING")
    else:
        blockers.append("JOIN_CARDINALITY_UNVERIFIED")
    blockers.extend([
        "PROVIDER_THREAD_ORIGINALITY_UNVERIFIED",
        "REPLY_CONTACT_IDENTITY_NOT_AUTHENTICATED",
        "TENANT_AUTHORITY_BINDING_NOT_PROVEN",
        "INBOUND_REPLY_SOURCE_AUTHENTICATION_NOT_PROVEN",
        "COMMERCIAL_INTENT_CLASSIFICATION_NOT_ATTESTED",
    ])
    return {
        "schema": "empire.conversation_reply_linkage_plan.v1",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "read_only_schema_sources": [str(DISCOVERY), str(GAP)],
        "legacy_gap_decision": gap_decision,
        "structural_reply_lineage": lineage_health,
        "controlled_identity_review": identity_review,
        "controlled_identity_review_not_live_evidence": True,
        "required_tables": {
            table: {
                "schema_present": table in columns,
                "missing_required_columns": fields,
            } for table, fields in missing.items()
        },
        "schema_join_path_available": complete_schema,
        "join_edges": join_edges,
        "verification_status": (
            "SCHEMA_PATH_FOUND_DATA_PROOF_REQUIRED"
            if complete_schema else "SCHEMA_INCOMPLETE"
        ),
        "blockers": blockers,
        "next_proof": [
            "Read-only bounded join probe over the three exact canonical tables",
            "Verify zero, one and multiple-match cases before using joins",
            "Verify original provider reply/thread metadata, not generated IDs",
            "Resolve tenant-scoped buyer/entity relationships from canonical authority",
            "Review privacy and suppression before any commercially consequential use",
        ],
        "contact_records_read": 0,
        "actual_joined_rows_proven": 0,
        "buyer_intent_verified": False,
        "canonical_messages_promoted": 0,
        "normalized_scores_written": 0,
        "database_access_attempted": False,
        "external_execution_authority": "none",
    }


def refresh(root: Path) -> dict[str, Any]:
    root = root.resolve()
    result = plan(
        _read(root / DISCOVERY), _read(root / GAP),
        market_gps=_read(root / "runtime/market_sweeps/revenue_gps_latest.json"),
    )
    target = root / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(target)
    return result
