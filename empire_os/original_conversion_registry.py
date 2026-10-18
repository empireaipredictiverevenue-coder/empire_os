"""Staged original-conversion-prediction registry contract for EmpireDB.

Never reuses the directional time-series registry. A prospective forecast
candidate is not evidence of durable recording until a *dedicated* audited
write, independent readback and authenticated tenant/clock proof exist.

No connection or mutation happens merely by importing this module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping, Protocol
import json

SCHEMA_VERSION = "empire.original_conversion_registry_preflight.v1"
MAX_CLOCK_DRIFT = timedelta(minutes=2)
MAX_RECORD_AGE = timedelta(minutes=5)


class OriginalConversionRegistryUnavailable(RuntimeError):
    pass


class OriginalConversionRegistryTransport(Protocol):
    def insert(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def readback(self, *, tenant_id: str, prediction_ref: str) -> Mapping[str, Any] | None: ...


def _timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or len(value) > 60:
        raise ValueError(f"{name} timestamp required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO8601") from exc
    if dt.utcoffset() is None:
        raise ValueError(f"{name} must include timezone")
    return dt.astimezone(timezone.utc)


def _preflight(candidate: Mapping[str, Any], *, as_of: datetime) -> tuple[str, dict[str, Any]]:
    if not isinstance(candidate, Mapping):
        raise ValueError("original candidate object required")
    if (candidate.get("schema_version") != "empire.original_conversion_prediction_preflight.v1"
            or candidate.get("status") != "REGISTRY_PROOF_REQUIRED"
            or candidate.get("original_prediction_registered") is not False
            or candidate.get("canonical_registry_readback_verified") is not False
            or candidate.get("database_writes") is not False
            or candidate.get("execution_authority") != "none"):
        raise ValueError("untrusted or already promoted prediction packet")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware review clock required")
    now = as_of.astimezone(timezone.utc)
    source = candidate.get("proposed_prediction")
    if not isinstance(source, Mapping):
        raise ValueError("candidate payload missing")
    if source.get("prediction_type") != "conversion_probability":
        raise ValueError("registry only accepts conversion_probability")
    required = {
        "tenant_id", "opportunity_key", "prediction_type", "predicted_probability",
        "predicted_at", "horizon_until", "model_name", "model_version",
        "evidence_refs", "prediction_ref",
    }
    if set(source) != required:
        raise ValueError("unexpected prediction payload keys")
    from empire_os.predictive_calibration import prepare_prospective_conversion_prediction
    parsed = prepare_prospective_conversion_prediction(
        tenant_id=source["tenant_id"],
        opportunity_key=source["opportunity_key"],
        predicted_probability=source["predicted_probability"],
        predicted_at=source["predicted_at"],
        horizon_until=source["horizon_until"],
        evidence_refs=source["evidence_refs"],
        model_name=source["model_name"],
        model_version=source["model_version"],
        assessed_at=now,
    )
    if (parsed["candidate_prediction_ref"] != source["prediction_ref"]
            or candidate.get("candidate_prediction_ref") != source["prediction_ref"]
            or dict(parsed["proposed_prediction"]) != dict(source)):
        raise ValueError("original candidate digest or payload mismatch")
    predicted = _timestamp(source["predicted_at"], "predicted_at")
    if now - predicted > MAX_RECORD_AGE:
        raise ValueError("prospective forecast too old to register")
    return source["prediction_ref"], dict(source)


def build_registration_request(
    candidate: Mapping[str, Any], *, as_of: datetime,
) -> dict[str, Any]:
    """Pure review; writer is never invoked by this function."""
    ref, prediction = _preflight(candidate, as_of=as_of)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "DB_MIGRATION_AND_AUTH_REQUIRED",
        "prediction_ref": ref,
        "tenant_id": prediction["tenant_id"],
        "payload": prediction,
        "db_recorded_at": None,
        "db_readback_verified": False,
        "original_prediction_registered": False,
        "time_safe_for_calibration": False,
        "conversion_outcome_known": False,
        "execution_authority": "none",
        "database_writes": False,
        "commercial_execution": False,
        "payment_execution": False,
    }


def inspect_prospective_registry_readback(
    candidate: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any] | None,
    readback: Mapping[str, Any] | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Compare a registry result against the actual proposed forecast.

    A caller-supplied dict is NOT an authenticated DB receipt. This function
    checks equality and plausible chronology only, and never certifies that
    the underlying DB, role, tenant binding or timestamp was authentic.
    """
    ref, prediction = _preflight(candidate, as_of=as_of)
    base = {
        "schema_version": "empire.original_conversion_registry_readback_review.v1",
        "prediction_ref": ref,
        "status": "READBACK_HOLD",
        "consistent": False,
        "reason": "authenticated_canonical_db_receipt_required",
        "database_timestamp_consistent": False,
        "tenant_identity_consistent": False,
        "immutable_registry_proven": False,
        "original_prediction_registered": False,
        "eligible_for_calibration": False,
        "commercial_execution": False,
        "execution_authority": "none",
    }
    if not isinstance(receipt, Mapping) or not isinstance(readback, Mapping):
        return base
    if (receipt.get("status") not in ("recorded", "existing")
            or receipt.get("prediction_ref") != ref
            or readback.get("prediction_ref") != ref
            or receipt.get("tenant_id") != prediction["tenant_id"]
            or readback.get("tenant_id") != prediction["tenant_id"]):
        return dict(base, reason="readback_identity_mismatch")
    receipt_clock = receipt.get("recorded_at")
    readback_clock = readback.get("recorded_at")
    try:
        stamped = _timestamp(receipt_clock, "recorded_at")
        copied = _timestamp(readback_clock, "readback_recorded_at")
        prepared = _timestamp(prediction["predicted_at"], "predicted_at")
    except ValueError:
        return dict(base, reason="readback_clock_missing")
    now = as_of.astimezone(timezone.utc)
    if not (stamped == copied and
            prepared - MAX_CLOCK_DRIFT <= stamped <= now + MAX_CLOCK_DRIFT and
            stamped < _timestamp(prediction["horizon_until"], "horizon_until")):
        return dict(base, reason="readback_timestamp_mismatch")
    expected = dict(prediction)
    actual = readback.get("prediction")
    if not isinstance(actual, Mapping) or dict(actual) != expected:
        return dict(base, reason="readback_payload_mismatch")
    if receipt.get("payload_sha256") != readback.get("payload_sha256"):
        return dict(base, reason="readback_hash_mismatch")
    canonical = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    if receipt.get("payload_sha256") != sha256(canonical.encode()).hexdigest():
        return dict(base, reason="readback_hash_incorrect")
    return dict(base,
        status="MATCHED_UNAUTHENTICATED_INPUT",
        reason="database_identity_and_timestamp_authentication_still_required",
        consistent=True,
        database_timestamp_consistent=True,
        tenant_identity_consistent=True,
    )
