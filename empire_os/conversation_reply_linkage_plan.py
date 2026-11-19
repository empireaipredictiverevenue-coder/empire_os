"""Read-only original reply -> conversation -> intent linkage design.

Uses observed DB schema metadata only, never message content, person records,
secret DSNs, DB writes or inferred commercial approvals.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Mapping
import json

from empire_os.reply_lineage_health import assess_reply_lineage
from empire_os.conversation_reply_binding_review import review_identity_bindings

DISCOVERY = Path("runtime/control_plane/conversations_replies_binding_truth_latest.json")
GAP = Path("runtime/control_plane/conversations_replies_identity_gap_latest.json")
OUTPUT = Path("runtime/conversations_replies_control/reply_linkage_plan_latest.json")
EXACT_JOIN = Path("runtime/conversations_replies_control/exact_reply_join_latest.json")
EXACT_PROOF_SCHEMA = "empire.reply_identity_lineage_structural_probe.v2"
EXACT_EDGES = [
    "public.outbound_replies.intent_id=public.outbound_intents.id",
    "public.empire_conversations.outbound_intent_id=public.outbound_replies.intent_id",
]
EXACT_COUNTS = (
    "intent_missing", "intent_unique", "intent_ambiguous",
    "conversation_missing", "conversation_unique", "conversation_ambiguous",
)
EXACT_METADATA_COUNTS = (
    "sent_email_intent_present", "active_email_context_present",
    "provider_message_field_present", "sender_field_present",
    "structurally_reviewable_not_authenticated",
    "email_intent_present", "suppressed_email_intent_present",
    "pending_email_intent_present", "non_email_intent_present",
)


def review_exact_join_proof(packet: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    """Present only fresh aggregate cardinality, never message/buyer identity."""
    held = {
        "status": "HELD_NO_TRUSTED_CURRENT_EXACT_JOIN_AGGREGATE",
        "query_completed": False,
        "reply_rows_observed": None,
        "replies_missing_conversation": None,
        "structurally_reviewable_not_authenticated": None,
        "buyer_intent_verified": False,
        "tenant_binding_verified": False,
        "provider_message_authenticated": False,
        "commercial_promotion_authorized": False,
        "execution_authority": "none",
    }
    if not isinstance(packet, Mapping) or now.tzinfo is None:
        return held
    try:
        stamp = datetime.fromisoformat(
            str(packet.get("generated_at")).replace("Z", "+00:00")
        )
    except ValueError:
        return held
    if stamp.tzinfo is None:
        return held
    age = now.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)
    if not timedelta(0) <= age <= timedelta(minutes=30):
        return held
    expected = {
        "schema_version": EXACT_PROOF_SCHEMA,
        "status": None,
        "mode": "OBSERVE",
        "source_query_completed": True,
        "read_only": True,
        "database_writes": False,
        "sample_limit": 100,
        "canonical_edges": EXACT_EDGES,
        "exact_join_cardinality_checked": True,
        "provider_thread_authenticated": False,
        "contact_authenticated": False,
        "tenant_authenticated": False,
        "buyer_intent_verified": False,
        "outbound_authorized": False,
        "admission_authorized": False,
        "crm_mutations": False,
        "raw_ids_or_pii_emitted": False,
        "execution_authority": "none",
    }
    if any(
        type(packet.get(k)) is not type(value) or packet.get(k) != value
        for k, value in expected.items() if k != "status"
    ):
        return held
    n = packet.get("reply_count")
    if type(n) is not int or not 0 <= n <= 100:
        return held
    if (packet.get("status") != (
            "NO_CANONICAL_REPLY_ROWS_IN_SAMPLE" if n == 0
            else "EXACT_CANONICAL_JOIN_STRUCTURAL_REVIEW_ONLY"
        ) or packet.get("sample_exhaustive") is not (n < 100)):
        return held
    counts = packet.get("structural_counts")
    meta = packet.get("read_only_metadata_counts")
    if not isinstance(counts, Mapping) or not isinstance(meta, Mapping):
        return held
    if (set(counts) != set(EXACT_COUNTS)
            or set(meta) != set(EXACT_METADATA_COUNTS)
            or any(type(v) is not int or not 0 <= v <= n
                   for v in list(counts.values()) + list(meta.values()))
            or sum(counts[k] for k in EXACT_COUNTS[:3]) != n
            or sum(counts[k] for k in EXACT_COUNTS[3:]) != n
            or meta["email_intent_present"] > counts["intent_unique"]
            or (meta["sent_email_intent_present"]
                + meta["suppressed_email_intent_present"]
                + meta["pending_email_intent_present"])
                > meta["email_intent_present"]
            or (meta["non_email_intent_present"] + meta["email_intent_present"])
                > counts["intent_unique"]
            or meta["active_email_context_present"] > counts["conversation_unique"]
            or meta["structurally_reviewable_not_authenticated"] > min(
                counts["intent_unique"], counts["conversation_unique"],
                meta["sent_email_intent_present"], meta["active_email_context_present"],
                meta["provider_message_field_present"], meta["sender_field_present"],
            )):
        return held
    return {
        **held,
        "status": "EXACT_CANONICAL_JOIN_AGGREGATE_OBSERVED_REVIEW_ONLY",
        "query_completed": True,
        "sample_exhaustive": packet["sample_exhaustive"],
        "generated_at": stamp.astimezone(timezone.utc).isoformat(),
        "reply_rows_observed": n,
        "replies_matching_intent": counts["intent_unique"],
        "replies_missing_conversation": counts["conversation_missing"],
        "replies_ambiguous_conversation": counts["conversation_ambiguous"],
        "replies_with_one_conversation": counts["conversation_unique"],
        "non_sent_email_intents": (
            meta["email_intent_present"] - meta["sent_email_intent_present"]
        ),
        "suppressed_email_intents": meta["suppressed_email_intent_present"],
        "sent_email_intent_count": meta["sent_email_intent_present"],
        "structurally_reviewable_not_authenticated": meta[
            "structurally_reviewable_not_authenticated"
        ],
    }


def _read_exact_join(root: Path) -> dict[str, Any] | None:
    source = root / EXACT_JOIN
    try:
        if (source.is_symlink() or not source.is_file()
                or not 0 < source.stat().st_size <= 10_000):
            return None
        value = json.loads(source.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None



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
    exact_join_probe: Mapping[str, Any] | None = None,
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
        "exact_join_observation": review_exact_join_proof(
            exact_join_probe, now=now
        ),
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
        exact_join_probe=_read_exact_join(root),
    )
    target = root / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(target)
    return result
