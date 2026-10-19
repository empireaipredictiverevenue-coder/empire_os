"""Source-timed Quant-to-original-conversion preflight; NO proof of a buyer.

Reuses the existing Quant Brain and original conversion candidate contract.
A source reference or externally supplied evidence object is never by itself
proof of first-party terms, registry custody, calibrated probability or sale.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping
import re

from empire_os.quant_brain import _DECISION_PACKET_REQUIRED, quant_decision_packet
from empire_os.predictive_calibration import prepare_prospective_conversion_prediction

SCHEMA = "empire.flagship.first_payer_quant_preflight.v1"
MAX_HORIZON_DAYS = 90
_REF = re.compile(r"^[a-z][a-z0-9_.:/-]{2,179}$")
_MODEL = frozenset(("probability_success", "uncertainty", "confidence"))
_FIELDS = frozenset(_DECISION_PACKET_REQUIRED)


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 60:
        raise ValueError("bounded original source timestamp required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid source timestamp") from exc
    if dt.utcoffset() is None:
        raise ValueError("source timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def review_first_payer_quant_preflight(
    *,
    tenant_id: str,
    opportunity_key: str,
    model_name: str,
    model_version: str,
    quant_inputs: Mapping[str, Any],
    source_receipts: Mapping[str, Mapping[str, Any]],
    assessed_at: datetime,
    horizon_days: int = 30,
) -> dict[str, Any]:
    """No DB writes, no buyer access, no inference of any missing Quant input."""
    if not isinstance(assessed_at, datetime) or assessed_at.utcoffset() is None:
        raise ValueError("trusted aware assessment clock required")
    now = assessed_at.astimezone(timezone.utc)
    if type(horizon_days) is not int or not 1 <= horizon_days <= MAX_HORIZON_DAYS:
        raise ValueError("bounded prospective forecast horizon required")
    for text in (tenant_id, opportunity_key, model_name, model_version):
        if (not isinstance(text, str) or not 0 < len(text) <= 128
                or text != text.strip()):
            raise ValueError("bounded tenant, opportunity, and model identity required")
    if not isinstance(quant_inputs, Mapping) or set(quant_inputs) - _FIELDS:
        raise ValueError("only canonical Quant decision fields allowed")
    if not isinstance(source_receipts, Mapping) or set(source_receipts) - _FIELDS:
        raise ValueError("only canonical Quant source fields allowed")

    missing = []
    unproven = []
    candidate_values: dict[str, float] = {}
    original_refs = set()
    for field in _DECISION_PACKET_REQUIRED:
        value = quant_inputs.get(field)
        if value is None:
            missing.append(field)
            continue
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError("only finite, non-boolean original numeric inputs accepted")
        if abs(value) > 1_000_000_000_000:
            raise ValueError("original economics input outside reviewed bounds")
        receipt = source_receipts.get(field)
        if not isinstance(receipt, Mapping):
            unproven.append(field)
            continue
        if set(receipt) != {"source_ref", "observed_at", "value", "source_class"}:
            raise ValueError("original evidence receipt shape mismatch")
        ref = receipt["source_ref"]
        if not isinstance(ref, str) or not _REF.fullmatch(ref):
            raise ValueError("bounded original evidence reference required")
        class_expected = "ORIGINAL_MODEL_OUTPUT" if field in _MODEL else "FIRST_PARTY_COMMERCIAL"
        if receipt["source_class"] != class_expected:
            raise ValueError("source authority class mismatch")
        if type(receipt["value"]) not in (int, float) or receipt["value"] != value:
            raise ValueError("original receipt differs from Quant value")
        moment = _utc(receipt["observed_at"])
        if moment > now:
            raise ValueError("future evidence cannot support prospective forecast")
        original_refs.add(ref)
        candidate_values[field] = float(value)

    report = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "status": "QUANT_EVIDENCE_INCOMPLETE",
        "missing_quant_fields": missing,
        "unsupported_original_source_fields": unproven,
        "original_source_reference_count": len(original_refs),
        "quant_status": "UNAVAILABLE",
        "quant_candidate_preview": None,
        "prospective_registry_preflight": None,
        "source_refs_authenticated_by_this_review": False,
        "buyer_identity_and_terms_authenticated": False,
        "buyer_market_capacity_authenticated": False,
        "model_probability_prospectively_attested": False,
        "forecast_durably_registered": False,
        "eligible_for_verified_outcome_calibration": False,
        "customer_accuracy_claim_authorized": False,
        "original_revenue_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "funds_moved": False,
        "model_weights_changed": False,
        "next_evidence_action": "OBTAIN_ORIGINAL_QUANT_INPUTS_AND_SOURCE_RECEIPTS",
    }
    if missing or unproven:
        return report
    if not original_refs:
        raise ValueError("missing original economic provenance")
    for name in ("probability_success", "uncertainty", "confidence"):
        if not 0 <= candidate_values[name] <= 1:
            raise ValueError("invalid prospective model probability or confidence")
    if candidate_values["time_to_revenue_days"] <= 0 or candidate_values["time_to_revenue_days"] > horizon_days:
        raise ValueError("economic timing exceeds prospective registration horizon")
    if not (candidate_values["revenue_low_cents"] <=
            candidate_values["conditional_revenue_cents"] <=
            candidate_values["revenue_high_cents"]):
        raise ValueError("commercial revenue point contradicts stated interval")
    if not (candidate_values["success_cost_low_cents"] <=
            candidate_values["success_cost_cents"] <=
            candidate_values["success_cost_high_cents"]):
        raise ValueError("commercial cost point contradicts stated interval")

    quant = quant_decision_packet(
        candidate_id=opportunity_key,
        inputs=candidate_values,
        trials=100,
        seed=0,
    )
    if quant.get("status") != "AVAILABLE" or quant.get("execution_authority") != "none":
        raise ValueError("existing Quant Brain did not accept original economics")
    prepared = prepare_prospective_conversion_prediction(
        tenant_id=tenant_id,
        opportunity_key=opportunity_key,
        predicted_probability=candidate_values["probability_success"],
        predicted_at=now.isoformat(),
        horizon_until=(now + timedelta(days=horizon_days)).isoformat(),
        evidence_refs=sorted(original_refs),
        model_name=model_name,
        model_version=model_version,
        assessed_at=now,
    )
    if (prepared["status"] != "REGISTRY_PROOF_REQUIRED"
            or prepared["original_prediction_registered"] is not False
            or prepared["may_use_in_verified_calibration"] is not False):
        raise ValueError("prospective registry cannot self-authorise evidence")
    return dict(
        report,
        status="QUANT_PREVIEW_UNAUTHENTICATED_ORIGINAL_EVIDENCE",
        quant_status="AVAILABLE",
        quant_candidate_preview={
            "schema_version": quant["schema_version"],
            "status": quant["status"],
            "prediction_only": True,
            "economics_simulated_not_realized": True,
            "model_weights_changed": False,
        },
        prospective_registry_preflight=prepared,
        next_evidence_action="INDEPENDENTLY_AUTHENTICATE_ORIGINAL_BUYER_TERMS_AND_MODEL_RECEIPTS",
    )
