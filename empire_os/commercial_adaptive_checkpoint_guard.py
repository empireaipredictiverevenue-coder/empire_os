"""Strict privacy-safe recovery of Ops Control's previous adaptive checkpoints.

Only whitelisted evidence counters, hashes and gate names survive a degraded
source cycle. The previous Ops snapshot is not a trusted deserialization format.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re

from empire_os.commercial_sales_director_adaptive_review import (
    KNOWN_ACTIONS, SCHEMA as SALES_SCHEMA, _digest as hash_json,
    _source_receipts,
)
from empire_os.commercial_adaptive_intelligence_control import (
    POLICY_LOOKUP, ALLOWED_SOURCE_STATES,
    SCHEMA as CONTROL_SCHEMA, _previous as validate_prior_control,
)
from empire_os.commercial_sales_director_original_proof import SAFE_SOURCE_BLOCKERS
from empire_os.revenue_distribution import SOURCES

HEX = re.compile(r"^[a-f0-9]{64}$")
SALES_FIELDS = {
    "schema_version", "mode", "execution_authority",
    "outbound_authorized", "database_writes", "agent_tasks_created",
    "operator_attention_due", "evidence_semantic_state",
    "evidence_semantic_hash", "owner_source_receipts",
}
CONTROL_FIELDS = {
    "schema_version", "mode", "execution_authority",
    "outbound_authorized", "database_writes", "agent_tasks_created",
    "payment_execution", "model_training", "owner_authority_changed",
    "decision_signature_data", "decision_signature", "gate_memory",
}
SALES_SEMANTIC = {
    "case_count", "action_counts", "owner_proof_counts",
    "source_blockers", "mailbox_observer",
    "casebook_source_refresh_required", "status",
}
SALES_PROOF_COUNTS = {
    "total_control_count", "verified_control_count",
    "canonical_message_count", "observed_inbound_reply_candidates",
    "authenticated_inbound_reply_count_verified", "verified_reply_join_count",
}
CONTROL_SIGNATURE = {
    "gates", "original_sales_case_counts", "original_reply_semantic",
    "offer_targets_from_reconstructed_source", "offer_ready", "catalog_ready",
    "missing_original_ids", "verified_person_and_email_source_claims",
    "original_source_claims_buyer_demand",
    "capacity_verified_source_claim", "terms_verified_source_claim",
    "buyers_activated_source_claim", "distribution_states",
    "upstream_offer_source_refresh",
}
MEMORY_KEYS = {
    "gate", "active", "ever_active", "consecutive_active_reviews",
    "lifetime_active_reviews", "resolutions", "recurrences",
}


def _int(value, *, nullable=False):
    return ((nullable and value is None)
            or (type(value) is int and 0 <= value <= 1_000_000))


def _record(value, keys):
    return isinstance(value, dict) and set(value) == keys


def recover_safe_adaptive_checkpoints(sales, commercial):
    """Return minimized validated replay packets, or (None, None) fail-closed."""
    try:
        if not isinstance(sales, dict) or not isinstance(commercial, dict):
            return None, None
        if not SALES_FIELDS.issubset(sales) or not CONTROL_FIELDS.issubset(commercial):
            return None, None
        if any(k not in sales for k in SALES_FIELDS):
            return None, None
        if len(json.dumps(sales, allow_nan=False)) > 80_000:
            return None, None
        if len(json.dumps(commercial, allow_nan=False)) > 80_000:
            return None, None
        if (
            sales["schema_version"] != SALES_SCHEMA
            or sales["mode"] != "OBSERVE"
            or sales["execution_authority"] != "none"
            or sales["outbound_authorized"] is not False
            or sales["database_writes"] is not False
            or sales["agent_tasks_created"] is not False
            or type(sales["operator_attention_due"]) is not bool
        ):
            return None, None
        state = sales["evidence_semantic_state"]
        if not _record(state, SALES_SEMANTIC) or sales["evidence_semantic_hash"] != hash_json(state):
            return None, None
        if (
            not _int(state["case_count"])
            or type(state["casebook_source_refresh_required"]) is not bool
            or state["status"] != "ORIGINAL_AUTHENTICATED_REPLY_EVIDENCE_HOLD"
            or state["mailbox_observer"] not in {
                "NO_COMPLETE_INBOUND_MESSAGE", "OBSERVER_ERROR",
                "VERIFIED_RUNTIME", "NOT_VERIFIED",
            }
        ):
            return None, None
        actions = state["action_counts"]
        if (not isinstance(actions, dict) or not set(actions).issubset(KNOWN_ACTIONS)
                or any(not _int(v) for v in actions.values())
                or sum(actions.values()) != state["case_count"]):
            return None, None
        proof = state["owner_proof_counts"]
        if not _record(proof, SALES_PROOF_COUNTS) or any(
            not _int(v, nullable=True) for v in proof.values()
        ):
            return None, None
        blockers = state["source_blockers"]
        if (not isinstance(blockers, list) or len(blockers) > 50
                or any(not isinstance(b, str) or b not in SAFE_SOURCE_BLOCKERS
                       for b in blockers)):
            return None, None
        receipts = _source_receipts(sales["owner_source_receipts"])

        signature = commercial["decision_signature_data"]
        if not _record(signature, CONTROL_SIGNATURE):
            return None, None
        if not isinstance(signature["gates"], list) or len(signature["gates"]) > 8:
            return None, None
        if len(set(signature["gates"])) != len(signature["gates"]):
            return None, None
        if not set(signature["gates"]).issubset(POLICY_LOOKUP):
            return None, None
        if (not isinstance(signature["original_reply_semantic"], str)
                or not HEX.fullmatch(signature["original_reply_semantic"])
                or signature["original_reply_semantic"] != sales["evidence_semantic_hash"]):
            return None, None
        for k in (
            "offer_targets_from_reconstructed_source", "offer_ready",
            "catalog_ready", "missing_original_ids",
            "verified_person_and_email_source_claims",
            "original_source_claims_buyer_demand",
        ):
            if not _int(signature[k]):
                return None, None
        for k in ("capacity_verified_source_claim", "terms_verified_source_claim",
                  "buyers_activated_source_claim"):
            if not _int(signature[k], nullable=True):
                return None, None
        ds = signature["distribution_states"]
        if (not isinstance(ds, dict) or set(ds) != set(SOURCES)
                or any(not isinstance(v, str) or v not in ALLOWED_SOURCE_STATES
                       for v in ds.values())):
            return None, None
        if type(signature["upstream_offer_source_refresh"]) is not bool:
            return None, None
        ca = signature["original_sales_case_counts"]
        if (not isinstance(ca, dict) or not set(ca).issubset(KNOWN_ACTIONS)
                or any(not _int(v) for v in ca.values())):
            return None, None
        memory = commercial["gate_memory"]
        if (not isinstance(memory, list) or len(memory) != len(POLICY_LOOKUP)
                or any(not _record(m, MEMORY_KEYS) for m in memory)):
            return None, None

        # Validate original integrity contract, then SELECT only known fields.
        validate_prior_control(commercial)
        safe_sales = {k: sales[k] for k in SALES_FIELDS if k != "owner_source_receipts"}
        safe_sales["owner_source_receipts"] = receipts
        safe_control = {k: commercial[k] for k in CONTROL_FIELDS}
        return safe_sales, safe_control
    except (TypeError, KeyError, ValueError, AttributeError, OverflowError):
        return None, None
