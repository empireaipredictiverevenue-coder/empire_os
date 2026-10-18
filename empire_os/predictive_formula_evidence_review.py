"""Founder-only evidence readiness for existing Predictive Revenue/Cloud formulae.

Reads two existing OBSERVE snapshots without refreshing producers. All source
counts are held when snapshots are stale/untrusted; no contact or product data
is copied into this operator summary, and no forecast is invented.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "empire.predictive_formula_evidence_review.v1"
SOURCES = {
    "cloud_formula": (
        "runtime/predictive_cloud/formula_latest.json",
        "empire.predictive_cloud_formula.runtime.v1",
        timedelta(hours=6),
    ),
    "revenue_distribution": (
        "runtime/revenue_distribution/latest.json",
        "empire.revenue_distribution.v1",
        timedelta(hours=24),
    ),
    "opportunity_quant": (
        "runtime/opportunity_factory/quant_review_latest.json",
        "empire.opportunity_quant_review.v1",
        timedelta(hours=6),
    ),
}
MAX_SOURCE_BYTES = 2_000_000
MAX_OPPORTUNITIES = 500
MAX_BLOCKERS = 60


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def _read_source(root: Path, key: str, as_of: datetime) -> tuple[str, dict[str, Any]]:
    relative, schema, max_age = SOURCES[key]
    file = root / relative
    try:
        # Do not follow untrusted links in an operator data surface.
        if (file.is_symlink() or file.parent.is_symlink()
                or (root / "runtime").is_symlink() or not file.is_file()):
            return "MISSING_OR_UNSAFE", {}
        size = file.stat().st_size
        if not 0 < size <= MAX_SOURCE_BYTES:
            return "UNTRUSTED", {}
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return "UNAVAILABLE", {}
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != schema
            or payload.get("mode") != "OBSERVE"
            or payload.get("execution_authority") != "none"):
        return "UNTRUSTED", {}
    observed_at = _stamp(payload.get("generated_at"))
    if observed_at is None:
        return "UNTRUSTED", {}
    age = as_of - observed_at
    if age < timedelta(0):
        return "FUTURE_HELD", {}
    if age > max_age:
        return "STALE", {}
    return "FRESH", payload


def review_formula_evidence(
    repo_root: str | Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    now = now.astimezone(timezone.utc)
    root = Path(repo_root).resolve(strict=False)
    cloud_status, cloud = _read_source(root, "cloud_formula", now)
    dist_status, distribution = _read_source(root, "revenue_distribution", now)
    quant_status, quant = _read_source(root, "opportunity_quant", now)
    blockers: list[str] = []
    ready = None
    evaluated = None
    cloud_blockers: list[str] = []
    if cloud_status == "FRESH":
        ready = cloud.get("prediction_ready")
        evaluated = cloud.get("formula_evaluated")
        if type(ready) is not bool or type(evaluated) is not bool:
            cloud_status = "UNTRUSTED"
            ready = evaluated = None
        else:
            raw = cloud.get("blockers")
            if (not isinstance(raw, list) or len(raw) > MAX_BLOCKERS
                    or not all(isinstance(r, str) and 0 < len(r) <= 120
                               and r.replace("_", "").isalnum() for r in raw)):
                cloud_status = "UNTRUSTED"
                ready = evaluated = None
            elif ready is True and raw:
                cloud_status = "UNTRUSTED"
                ready = evaluated = None
            else:
                cloud_blockers = sorted(set(raw))
    if cloud_status != "FRESH":
        blockers.append(f"cloud_formula:{cloud_status.lower()}")
    else:
        if ready is False:
            blockers.extend(cloud_blockers or ["verified_probability_or_economics_required"])
        if evaluated is False:
            blockers.append("cloud_formula_not_yet_evaluated")

    opportunity_count: int | None = None
    bounds_supported: bool | None = None
    missing_counts: dict[str, int] | None = None
    if dist_status == "FRESH":
        rows = distribution.get("opportunities")
        if not isinstance(rows, list) or len(rows) > MAX_OPPORTUNITIES:
            dist_status = "UNTRUSTED"
        else:
            names: set[str] = set()
            missing: Counter[str] = Counter()
            can_parse = True
            bounds_supported = True
            for row in rows:
                if not isinstance(row, Mapping):
                    can_parse = False
                    break
                key = row.get("opportunity_key")
                if not isinstance(key, str) or not key or key in names:
                    can_parse = False
                    break
                names.add(key)
                prediction = row.get("canonical_prediction")
                if (not isinstance(prediction, Mapping)
                        or prediction.get("schema_version") != "empire.predictive_revenue.formula.v1"
                        or prediction.get("status") not in ("AVAILABLE", "UNAVAILABLE")):
                    can_parse = False
                    break
                unknown = prediction.get("missing_fields", [])
                if not isinstance(unknown, list) or len(unknown) > 20:
                    can_parse = False
                    break
                if any(not isinstance(name, str) or
                       name not in (*_CORE_FACTORS, "ltv_cents") for name in unknown):
                    can_parse = False
                    break
                missing.update(set(unknown))
                bounds = row.get("canonical_prediction_identification_bounds")
                if (not isinstance(bounds, Mapping)
                        or bounds.get("schema_version") != "empire.predictive_revenue.bounds.v1"
                        or (prediction["status"] == "AVAILABLE"
                            and bounds.get("status") != "FULLY_SPECIFIED_SCENARIO")
                        or (prediction["status"] == "UNAVAILABLE"
                            and bounds.get("status") not in (
                                "PARTIALLY_IDENTIFIED", "UNAVAILABLE"
                            ))):
                    bounds_supported = False
            if can_parse:
                opportunity_count = len(rows)
                missing_counts = dict(sorted(missing.items()))
            else:
                dist_status = "UNTRUSTED"
                bounds_supported = None
    if dist_status != "FRESH":
        blockers.append(f"revenue_distribution:{dist_status.lower()}")
    elif bounds_supported is False:
        blockers.append("revenue_distribution_formula_bounds_not_yet_deployed")
    if missing_counts:
        blockers.append("revenue_formula_inputs_incomplete")
    if dist_status == "FRESH" and opportunity_count == 0:
        blockers.append("no_observed_opportunities_for_formula")

    quant_counts = _quant_review_counts(quant) if quant_status == "FRESH" else None
    if quant_status == "FRESH" and quant_counts is None:
        quant_status = "UNTRUSTED"

    # Same authenticated Economic Memory/Quant benchmark as the existing
    # shadow learning subsystem. Never trust a serialized performance number
    # as proof, or expose per-tenant learning in this global founder response.
    from empire_os.predictive_learning_readiness import read_founder_learning_readiness
    learning = read_founder_learning_readiness(root, as_of=now)

    current = cloud_status == "FRESH" and dist_status == "FRESH"
    status = (
        "REVIEW_READY" if current and ready is True and evaluated is True
        and bounds_supported is True and opportunity_count is not None
        and opportunity_count > 0 and not missing_counts
        else "EVIDENCE_HOLD"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source_status": {
            "cloud_formula": cloud_status,
            "revenue_distribution": dist_status,
            "opportunity_quant": quant_status,
        },
        "cloud_prediction_ready": ready,
        "cloud_formula_evaluated": evaluated,
        "cloud_formula_blockers": cloud_blockers if cloud_status == "FRESH" else [],
        "fresh_opportunity_count": opportunity_count,
        "revenue_formula_bounds_supported": bounds_supported,
        "missing_factor_counts": missing_counts,
        "quant_original_prediction_readiness": quant_counts,
        "verified_outcome_learning": learning,
        "blockers": sorted(set(blockers)),
        "model_is_commercially_calibrated": False,
        "source_reports_are_not_independent_payment_proof": True,
        "forecast_generated_by_this_review": False,
        "commercial_execution_authorized": False,
        "outbound_sent": False,
        "payments_moved": False,
        "execution_authority": "none",
    }


from empire_os.predictive_revenue_formula import CORE_FACTORS as _CORE_FACTORS


def _quant_review_counts(source: Mapping[str, Any]) -> dict[str, Any] | None:
    """Recompute Quant's summary without reading/providing customer details."""
    from empire_os.quant_brain import _DECISION_PACKET_REQUIRED

    entries = source.get("items")
    if not isinstance(entries, list) or len(entries) > MAX_OPPORTUNITIES:
        return None
    unique: set[str] = set()
    missing: Counter[str] = Counter()
    available = 0
    for row in entries:
        if not isinstance(row, Mapping):
            return None
        key = row.get("opportunity_key")
        if not isinstance(key, str) or not key or key in unique:
            return None
        unique.add(key)
        packet = row.get("decision_packet")
        if not isinstance(packet, Mapping):
            return None
        status = packet.get("status")
        if status not in ("AVAILABLE", "UNAVAILABLE"):
            return None
        factors = packet.get("missing_fields", [])
        if (not isinstance(factors, list) or len(factors) > 30
                or any(
                    not isinstance(factor, str)
                    or factor not in _DECISION_PACKET_REQUIRED
                    for factor in factors
                ) or len(set(factors)) != len(factors)):
            return None
        if status == "AVAILABLE":
            if factors or not isinstance(row.get("prediction_ref"), str):
                return None
            available += 1
        elif not factors or row.get("prediction_ref") is not None:
            return None
        missing.update(factors)

    expected = {
        "candidate_count": len(entries),
        "available_decision_packet_count": available,
        "unavailable_decision_packet_count": len(entries) - available,
    }
    if any(type(source.get(name)) is not int or source[name] != value
           for name, value in expected.items()):
        return None
    declared = source.get("missing_field_counts")
    if not isinstance(declared, Mapping) or dict(declared) != dict(missing):
        return None
    return {
        "candidate_count": len(entries),
        "available_quant_decision_count": available,
        "missing_quant_economics_count": len(entries) - available,
        "missing_input_counts": dict(sorted(missing.items())),
        "source_rows_are_original_conversion_predictions": False,
        "immutable_prediction_receipt_verified": False,
        "next_evidence_action": (
            "RECORD_TIMESTAMPED_CONVERSION_PREDICTION"
            if available > 0 else "VERIFY_ORIGINAL_QUANT_INPUT_ECONOMICS"
        ),
    }
