"""Safe read-only Conversations & Replies proof status for EXISTING Founder Ops.

This produces only aggregate, allowlisted proof states; it does not expose
message content, contact identities, raw provider events or credentials.
No new worker, timer, DB read, writes, external model or outbound authority.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA="empire.conversation_control_operational_truth.v1"
EXPECTED=frozenset({
    "action_authority","canonical_identity","conflict_detection",
    "duplicate_detection","entity_classification","evidence_lineage",
    "freshness","input_quality","outcome_linkage","output_quality","quarantine",
})
SOURCE_PATHS={
    "bindings":"runtime/control_plane/runtime_control_bindings_latest.json",
    "collector":"runtime/conversations_replies_control/latest.json",
    "health":"runtime/conversations_replies_control/collector_health_latest.json",
    "linkage":"runtime/conversations_replies_control/reply_linkage_plan_latest.json",
    "identity_discovery":"runtime/control_plane/conversations_replies_binding_truth_latest.json",
    "identity_gap":"runtime/control_plane/conversations_replies_identity_gap_latest.json",
}
ACTIONS=(
    "Verify original inbound provider event and authoritative message/thread IDs",
    "Verify exact canonical reply -> intent -> conversation joins, including 0/1/multiple matches",
    "Bind real sender contact and tenant through existing canonical identity controls",
    "Retain suppression and privacy controls before any reply-derived commercial action",
    "Verify a genuine reply classification/outcome before promoting output or revenue claims",
)


def _read(root: Path, key: str) -> Mapping[str, Any] | None:
    path=root/SOURCE_PATHS[key]
    try:
        if path.stat().st_size>2_000_000:
            return None
        obj=json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj,dict) else None
    except (OSError,ValueError):
        return None


def _old(record: Mapping[str, Any] | None, *, now: datetime) -> bool:
    if record is None:
        return True
    raw=record.get("generated_at")
    try:
        observed=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        if observed.tzinfo is None:
            return True
        duration=now-observed.astimezone(timezone.utc)
        return not timedelta(0)<=duration<=timedelta(days=7)
    except ValueError:
        return True


def _nonnegative_count(value: Any) -> int | None:
    return value if type(value) is int and 0<=value<=1_000_000_000 else None


def inspect_conversation_evidence(
    root: Path, *, now: datetime | None=None,
) -> dict[str, Any]:
    assessed=now or datetime.now(timezone.utc)
    if assessed.tzinfo is None:
        raise ValueError("aware assessment time required")
    assessed=assessed.astimezone(timezone.utc)
    docs={key:_read(root,key) for key in SOURCE_PATHS}
    binding=docs["bindings"]
    control_rows={}
    if isinstance(binding,Mapping) and binding.get("authority")=="OBSERVE":
        lanes=binding.get("lanes")
        if isinstance(lanes,list):
            matches=[row.get("controls") for row in lanes
                     if isinstance(row,dict) and row.get("lane")=="conversations_replies"]
            if len(matches)==1 and isinstance(matches[0],dict):
                control_rows=matches[0]
    supported=(set(control_rows)==EXPECTED and all(
        isinstance(v,dict)
        and v.get("lane")=="conversations_replies"
        and v.get("control")==key
        and v.get("status") in {"VERIFIED_RUNTIME","UNVERIFIED","HOLD","HOLD_REVIEW_REQUIRED"}
        and v.get("action_authority_granted") is not True
        for key,v in control_rows.items()))
    verified=sorted(
        key for key,detail in control_rows.items()
        if isinstance(detail,Mapping)
        and detail.get("status")=="VERIFIED_RUNTIME"
        and key in EXPECTED
    ) if supported else []
    missing=sorted(EXPECTED-set(verified)) if supported else sorted(EXPECTED)
    collector=docs["collector"] or {}
    health=docs["health"] or {}
    linkage=docs["linkage"] or {}
    summary=collector.get("semantic_effectiveness")
    summary=summary if isinstance(summary,dict) else {}
    admission=collector.get("source_admission")
    admission=admission if isinstance(admission,dict) else {}
    admitted=_nonnegative_count(admission.get("admitted_conversation_candidate_rows"))
    canonical=_nonnegative_count(summary.get("canonical_message_count"))
    inbound=_nonnegative_count(summary.get("inbound_reply_count"))
    joined=_nonnegative_count(linkage.get("actual_joined_rows_proven"))
    tenant=admission.get("tenant_binding_established") is True
    linkage_ready=(
        linkage.get("verification_status")=="VERIFIED_RUNTIME"
        and joined is not None and joined>0
    )
    # No inferred buyer intent, even if an internal control is marked VERIFIED.
    source_ready=bool(
        health.get("status")=="READ_SUCCESS"
        and collector.get("mode")=="OBSERVE"
        and linkage.get("mode")=="OBSERVE"
    )
    # Arbitrary source text is never passed through to the Founder API.
    approved_blockers=frozenset({
        "SCHEMA_COLUMNS_MISSING","JOIN_CARDINALITY_UNVERIFIED",
        "PROVIDER_THREAD_ORIGINALITY_UNVERIFIED",
        "REPLY_CONTACT_IDENTITY_NOT_AUTHENTICATED",
        "TENANT_AUTHORITY_BINDING_NOT_PROVEN",
        "INBOUND_REPLY_SOURCE_AUTHENTICATION_NOT_PROVEN",
        "COMMERCIAL_INTENT_CLASSIFICATION_NOT_ATTESTED",
    })
    blockers=sorted(approved_blockers.intersection(
        str(x) for x in (linkage.get("blockers") or [])
        if isinstance(x,str)
    ))
    if canonical is None or canonical==0:
        blockers.append("NO_CANONICAL_INBOUND_MESSAGES_VERIFIED")
    if not supported:
        blockers.append("CANONICAL_CONTROL_SCHEMA_UNVERIFIED")
    if not source_ready:
        blockers.append("LIVE_COLLECTOR_OR_LINKAGE_NOT_READY")
    stale=sorted(k for k in ("identity_discovery","identity_gap")
                 if _old(docs[k],now=assessed))
    if stale:
        blockers.append("IDENTITY_DISCOVERY_EVIDENCE_STALE_OR_MISSING")
    blockers=sorted(set(blockers))
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"HOLD_REAL_REPLY_EVIDENCE_REQUIRED",
        "canonical_control_schema_verified":supported,
        "verified_control_count":len(verified),
        "total_control_count":len(EXPECTED),
        "verified_internal_controls":verified,
        "unverified_controls":missing,
        "original_candidate_count":admitted,
        "canonical_message_count":canonical,
        "observed_inbound_reply_candidate_count":inbound,
        "authenticated_inbound_reply_count_verified":None,
        "verified_reply_join_count":joined if joined is not None else 0,
        "tenant_binding_claimed_in_collector":tenant,
        "tenant_binding_independently_verified":False,
        "linkage_verification_ready":linkage_ready,
        "collector_source_read_verified":source_ready,
        "stale_identity_metadata_sources":stale,
        "source_blockers":blockers,
        "next_evidence_actions":list(ACTIONS),
        "internal_control_proof_not_buyer_intent":True,
        "buyer_intent_verified":False,
        "authenticated_reply_identity_verified":False,
        "automatic_promotion_authorized":False,
        "message_bodies_disclosed":False,
        "personal_identities_disclosed":False,
        "source_values_disclosed":False,
        "customer_delivery_enabled":False,
        "outbound_enabled":False,
        "payment_execution":False,
        "database_writes":False,
        "execution_authority":"NONE",
    }
