"""Read-only bounded bridge to the EXISTING single-ref conversion registry.

An approved existing reader supplies only explicitly named forecast refs.
A returned dictionary is not independently authenticated proof of registry
completeness, immutability, or a commercial success. No model training.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping, Protocol, Sequence
import json
import re

from empire_os.flagship_forecast_population_audit import (
    MANIFEST_SCHEMA, _prediction, _when, review_forecast_population,
)

SCHEMA = "empire.flagship.original_forecast_known_ref_bridge.v1"
REF = re.compile(r"^conversion_prediction_candidate:[0-9a-f]{32}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_REFS = 100


class OriginalPredictionReader(Protocol):
    def readback(
        self, *, tenant_id: str, prediction_ref: str
    ) -> Mapping[str, Any] | None: ...


def review_known_original_forecasts(
    memory: Mapping[str, Any], *,
    tenant_id: str,
    prediction_refs: Sequence[str],
    as_of: datetime,
    reader: OriginalPredictionReader | None = None,
    approved_readonly: bool = False,
) -> dict[str, Any]:
    """Validate explicit known-ref readbacks; never infer full inventory."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware audit clock required")
    now = as_of.astimezone(timezone.utc)
    if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 128:
        raise ValueError("explicit tenant scope required")
    if not isinstance(prediction_refs, (list, tuple)) or len(prediction_refs) > MAX_REFS:
        raise ValueError("bounded list of original refs required")
    if (any(not isinstance(ref, str) or not REF.fullmatch(ref)
            for ref in prediction_refs)
            or len(set(prediction_refs)) != len(prediction_refs)):
        raise ValueError("distinct original candidate refs required")

    prior = review_forecast_population(memory, tenant_id=tenant_id, as_of=now)
    report = {
        "schema_version": SCHEMA,
        "status": "READ_ONLY_NOT_AUTHORISED",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "known_refs_requested": len(prediction_refs),
        "known_refs_matched": None,
        "known_refs_missing": None,
        "known_refs_population_review": None,
        "canonical_verified_pairs": prior["verified_economic_memory_paired_reviews"],
        "complete_registry_population_verified": False,
        "authenticated_session_proven_by_bridge": False,
        "source_immutability_proven_by_bridge": False,
        "customer_accuracy_claim_authorized": False,
        "model_weight_mutation": False,
        "database_writes": False,
        "outbound_sent": False,
        "payment_execution": False,
    }
    if approved_readonly is not True:
        return report
    if reader is None or not callable(getattr(reader, "readback", None)):
        raise ValueError("existing authorised read-only registry reader required")
    if not prediction_refs:
        return dict(report, status="NO_KNOWN_REFS", known_refs_matched=0, known_refs_missing=0)

    records = []
    missing = 0
    for ref in prediction_refs:
        # Existing tenant-scoped per-ref reader only. No SQL or bulk access.
        snapshot = reader.readback(tenant_id=tenant_id, prediction_ref=ref)
        if snapshot is None:
            missing += 1
            continue
        if not isinstance(snapshot, Mapping) or set(snapshot) != {
            "prediction_ref", "tenant_id", "recorded_at",
            "payload_sha256", "prediction",
        } or snapshot["prediction_ref"] != ref or snapshot["tenant_id"] != tenant_id:
            raise ValueError("registry reader response identity mismatch")
        row = snapshot["prediction"]
        _prediction(row, tenant_id, now)
        if row["prediction_ref"] != ref:
            raise ValueError("nested original prediction identity mismatch")
        recorded, predicted, horizon = (
            _when(snapshot["recorded_at"]),
            _when(row["predicted_at"]),
            _when(row["horizon_until"]),
        )
        if not predicted - timedelta(minutes=2) <= recorded <= now or recorded >= horizon:
            raise ValueError("registry chronology mismatch")
        digest = snapshot["payload_sha256"]
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("original digest missing")
        canonical = json.dumps(
            row, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode()
        if sha256(canonical).hexdigest() != digest:
            raise ValueError("original payload digest mismatch")
        records.append({
            "prediction": dict(row),
            "registry_recorded_at": recorded.isoformat(),
            "reader_observed_at": now.isoformat(),
        })

    if missing:
        return dict(report, status="KNOWN_REF_READBACK_INCOMPLETE",
                    known_refs_matched=len(records), known_refs_missing=missing)
    reconciled = review_forecast_population(
        memory, tenant_id=tenant_id, as_of=now,
        manifest={
            "schema_version": MANIFEST_SCHEMA,
            "mode": "OBSERVE", "tenant_id": tenant_id, "records": records,
        },
    )
    keys = (
        "supplied_forecast_count", "matched_terminal_win", "matched_terminal_loss",
        "pending_before_horizon", "horizon_elapsed_unverified",
        "unmatched_memory_predictions", "next_evidence_action",
    )
    return dict(report, status="KNOWN_REF_DESCRIPTIVE_RECONCILIATION_ONLY",
                known_refs_matched=len(records), known_refs_missing=0,
                known_refs_population_review={key: reconciled[key] for key in keys})
