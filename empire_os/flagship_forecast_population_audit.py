"""Read-only forecast-universe maturity audit, not a second calibration model.

Uses the existing, fully revalidated Economic Memory and shadow benchmark.
An inventory supplied as a mapping is NOT authenticated EmpireDB evidence:
only the original registry's approved tenant-bound reader could establish that.
No missing outcome is ever converted into a failure label.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from empire_os.lead_shadow_calibration_benchmark import evaluate_shadow_calibration

SCHEMA = "empire.flagship.forecast_population_audit.v1"
MANIFEST_SCHEMA = "empire.original_conversion_population_untrusted_export.v1"
MAX_FORECASTS = 500
_REQUIRED = frozenset((
    "tenant_id", "opportunity_key", "prediction_ref", "prediction_type",
    "predicted_probability", "predicted_at", "horizon_until", "evidence_refs",
))
_OPTIONAL = frozenset(("model_name", "model_version"))


def _when(value: Any) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 60:
        raise ValueError("bounded, timezone-aware evidence timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid evidence timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 240 and value == value.strip()


def _prediction(row: Mapping[str, Any], tenant_id: str, now: datetime) -> tuple[datetime, datetime]:
    if not isinstance(row, Mapping) or not _REQUIRED <= row.keys() or row.keys() - (_REQUIRED | _OPTIONAL):
        raise ValueError("original prediction schema mismatch")
    if ("model_name" in row) != ("model_version" in row):
        raise ValueError("incomplete original model identity")
    if (row["tenant_id"] != tenant_id
            or row["prediction_type"] != "conversion_probability"
            or any(not _identifier(row[key]) for key in (
                "tenant_id", "opportunity_key", "prediction_ref"
            ))):
        raise ValueError("prediction tenant or original identity mismatch")
    for key in ("model_name", "model_version"):
        if key in row and not _identifier(row[key]):
            raise ValueError("invalid model identity")
    probability = row["predicted_probability"]
    if type(probability) not in (int, float) or not isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("finite genuine probability required")
    refs = row["evidence_refs"]
    if not isinstance(refs, (tuple, list)) or not 1 <= len(refs) <= 20 or any(
        not _identifier(ref) for ref in refs
    ) or len(set(refs)) != len(refs):
        raise ValueError("original evidence lineage required")
    predicted, horizon = _when(row["predicted_at"]), _when(row["horizon_until"])
    if not predicted < horizon or predicted > now:
        raise ValueError("prediction chronology impossible")
    return predicted, horizon


def review_forecast_population(
    memory: Mapping[str, Any], *, tenant_id: str | None,
    as_of: datetime, manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess matched terminals and unresolved forecasts without changing labels.

    The caller MUST independently authenticate and prove complete any future
    production inventory. A caller-supplied manifest never establishes that.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware audit clock required")
    now = as_of.astimezone(timezone.utc)
    # Bound all supplied collections before handing them to the original
    # validator; do not accept an unlimited foreign Economic Memory object.
    if not isinstance(memory, Mapping):
        raise ValueError("canonical economic memory required")
    if any(not isinstance(memory.get(key), list)
           or len(memory[key]) > MAX_FORECASTS
           for key in ("calibration_evidence", "verified_learning_feedback")):
        raise ValueError("bounded canonical learning records required")
    if memory.get("generated_at") is not None and _when(memory["generated_at"]) > now:
        raise ValueError("future economic memory snapshot")
    # Canonical benchmark rejects tampered reviews, future evidence, duplicates,
    # cross-tenant outcomes, unsafe memory and unverified terminal labels.
    prior = evaluate_shadow_calibration(
        memory, tenant_id=tenant_id, as_of=now
    )
    base = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "as_of": now.isoformat(),
        "verified_economic_memory_paired_reviews": prior["verified_review_count"],
        "unpaired_verified_feedback": prior["unpaired_verified_outcome_count"],
        "supplied_forecast_count": None,
        "matched_terminal_win": None,
        "matched_terminal_loss": None,
        "pending_before_horizon": None,
        "horizon_elapsed_unverified": None,
        "unmatched_memory_predictions": None,
        "matured_unknowns_counted_as_losses": False,
        "manifest_is_authenticated_registry_readback": False,
        "complete_registered_forecast_denominator_verified": False,
        "selection_bias_excluded": False,
        "scientific_precision_claim_authorized": False,
        "automatic_model_calibration": False,
        "model_weight_mutation": False,
        "database_writes": False,
        "outbound_authorized": False,
        "payment_execution": False,
    }
    if manifest is None:
        return dict(base, status="FORECAST_UNIVERSE_NOT_SUPPLIED",
                    next_evidence_action="OBTAIN_APPROVED_AUTHENTICATED_FORECAST_REGISTRY_INVENTORY")
    if not _identifier(tenant_id):
        raise ValueError("tenant-scoped registry manifest required")
    if not isinstance(manifest, Mapping) or set(manifest) != {
        "schema_version", "mode", "tenant_id", "records",
    } or manifest["schema_version"] != MANIFEST_SCHEMA or manifest["mode"] != "OBSERVE" or manifest["tenant_id"] != tenant_id:
        raise ValueError("untrusted or cross-tenant population export")
    records = manifest["records"]
    if not isinstance(records, list) or len(records) > MAX_FORECASTS:
        raise ValueError("bounded forecast list required")

    canonical = {}
    for row in memory["calibration_evidence"]:
        ref = row["prediction_ref"]
        canonical[ref] = row
    refs = set()
    opportunities = set()
    wins = losses = pending = matured_unverified = 0
    for item in records:
        if not isinstance(item, Mapping) or set(item) != {
            "prediction", "registry_recorded_at", "reader_observed_at",
        }:
            raise ValueError("unexpected population source fields")
        row = item["prediction"]
        predicted, horizon = _prediction(row, tenant_id, now)
        recorded, readback = _when(item["registry_recorded_at"]), _when(item["reader_observed_at"])
        # The existing original registry tolerates a predicted-at timestamp
        # up to two minutes ahead of its trusted registration clock.
        if not predicted - timedelta(minutes=2) <= recorded <= readback <= now or recorded >= horizon:
            raise ValueError("missing prospective registry chronology")
        ref, opportunity = row["prediction_ref"], row["opportunity_key"]
        if ref in refs or opportunity in opportunities:
            raise ValueError("duplicate population prediction or opportunity")
        refs.add(ref)
        opportunities.add(opportunity)
        review = canonical.get(ref)
        if review is None:
            if now < horizon:
                pending += 1
            else:
                matured_unverified += 1  # NEVER infer verified zero/negative.
        else:
            if dict(row) != dict(review["prediction"]):
                raise ValueError("registered forecast differs from validated economic memory")
            # Original forecast must have been recorded before an outcome
            # was independently captured, not reconstructed after a win.
            outcome_at = _when(review["feedback"]["outcome_recorded_at"])
            if not recorded < outcome_at:
                raise ValueError("registry candidate observed after terminal outcome")
            if review["actual_value"] == 1:
                wins += 1
            else:
                losses += 1

    orphaned = len(set(canonical) - refs)
    if orphaned or prior["unpaired_verified_outcome_count"]:
        next_action = "RECONCILE_ALL_ORIGINAL_FORECASTS_AND_OUTCOMES"
    elif not records:
        next_action = "CAPTURE_FIRST_APPROVED_ORIGINAL_FORECAST"
    elif matured_unverified:
        next_action = "RESOLVE_MATURED_UNKNOWN_OUTCOMES_WITH_ORIGINAL_EVIDENCE"
    else:
        next_action = "VERIFY_COMPLETE_IMMUTABLE_FORECAST_REGISTRY_EXPORT"
    return dict(
        base,
        status="UNAUTHENTICATED_MANIFEST_REVIEW_ONLY",
        supplied_forecast_count=len(records),
        matched_terminal_win=wins,
        matched_terminal_loss=losses,
        pending_before_horizon=pending,
        horizon_elapsed_unverified=matured_unverified,
        unmatched_memory_predictions=orphaned,
        next_evidence_action=next_action,
    )
