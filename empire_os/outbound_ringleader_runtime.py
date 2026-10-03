"""OBSERVE-only Ringleader persistence runtime.

This component normalizes provider evidence, chains it into the Reputation Passport,
persists append-only observations in EmpireDB, evaluates Ringleader, and records the
decision. It never sends mail or authorizes mutation.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from empire_os.outbound_deliverability_ringleader import evaluate_ringleader
from empire_os.outbound_evidence_chain import GENESIS, chain_evidence
from empire_os.outbound_evidence_normalizer import normalize_evidence


class EvidenceReader(Protocol):
    def latest_evidence_head(self) -> str | None:
        ...


class EvidenceWriter(Protocol):
    def append_observation(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def append_decision(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


def _decision_key(
    scope_key: str,
    observed_at: str,
    result: Mapping[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "scope_key": scope_key,
            "observed_at": observed_at,
            "posture": result.get("posture"),
            "hard_holds": result.get("hard_holds") or [],
            "tasks": result.get("tasks") or [],
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def persist_evidence_and_decision(
    *,
    scope_key: str,
    source: str,
    provider_payload: Mapping[str, Any],
    ringleader_context: Mapping[str, Any],
    reader: EvidenceReader,
    writer: EvidenceWriter,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Persist evidence and Ringleader decision while remaining OBSERVE-only."""

    scope = str(scope_key or "").strip()
    if not scope:
        raise ValueError("scope_key_required")

    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed_iso = now.isoformat()

    head = reader.latest_evidence_head() or GENESIS
    persisted: list[dict[str, Any]] = []

    normalized = normalize_evidence(
        source,
        {
            **dict(provider_payload),
            "observed_at": provider_payload.get("observed_at") or observed_iso,
        },
    )

    for row in normalized:
        chain_material = {
            "scope_key": scope,
            "source": row["source"],
            "observed_at": row["observed_at"],
            "domain": row.get("domain"),
            "mailbox_key": row.get("mailbox_key"),
            "transport_key": row.get("transport_key"),
            "recipient_mx": row.get("recipient_mx"),
            "metric_name": row["metric_name"],
            "metric_value": row.get("metric_value"),
            "unit": row.get("unit"),
            "evidence": row.get("evidence") or {},
        }
        chained = chain_evidence(chain_material, previous_hash=head)
        stored = {
            **row,
            "evidence": chain_material,
            "evidence_hash": chained["evidence_hash"],
            "previous_evidence_hash": chained["previous_evidence_hash"],
        }
        write_result = writer.append_observation(stored)
        persisted.append({
            "id": write_result["id"],
            "metric_name": row["metric_name"],
            "evidence_hash": chained["evidence_hash"],
        })
        head = chained["evidence_hash"]

    decision = evaluate_ringleader(ringleader_context)
    if decision.get("mutation_authorized") is not False:
        raise RuntimeError("ringleader_runtime_must_remain_observe_only")

    decision_material = {
        "scope_key": scope,
        "observed_at": observed_iso,
        "posture": decision["posture"],
        "hard_holds": decision.get("hard_holds") or [],
        "tasks": decision.get("tasks") or [],
        "ringleader": decision,
    }
    chained_decision = chain_evidence(decision_material, previous_hash=head)
    decision_key = _decision_key(scope, observed_iso, decision)

    decision_write = writer.append_decision({
        "decision_key": decision_key,
        "observed_at": now,
        "posture": decision["posture"],
        "domain": dict(ringleader_context.get("domain_sovereignty") or {}).get("domain"),
        "mailbox_key": ringleader_context.get("mailbox_key"),
        "transport_key": ringleader_context.get("transport_key"),
        "recipient_mx": ringleader_context.get("recipient_mx"),
        "hard_holds": decision.get("hard_holds") or [],
        "tasks": decision.get("tasks") or [],
        "evidence": decision_material,
        "mutation_authorized": False,
        "evidence_hash": chained_decision["evidence_hash"],
        "previous_evidence_hash": chained_decision["previous_evidence_hash"],
    })

    return {
        "scope_key": scope,
        "observations_persisted": persisted,
        "decision_id": decision_write["id"],
        "decision_key": decision_key,
        "posture": decision["posture"],
        "head_hash": chained_decision["evidence_hash"],
        "mutation_authorized": False,
    }
