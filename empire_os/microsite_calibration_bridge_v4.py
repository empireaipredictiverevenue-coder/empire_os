"""Shadow calibration of microsite demand models using original Predictive V3 methods.

The source-custody checker is supplied by the *original* observation owner; a
caller-written provenance string, numeric score or booleans alone are NOT proof.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any

from empire_os.predictive_materializer import materialize_daily_actuals
from empire_os.predictive_calibration import (
    ForecastActualEvidence, review_forecast_calibration,
)


def review_historical_model_calibration(
    cases: Sequence[Mapping[str, Any]], *,
    verify_original_source: Callable[[str, str, tuple[str, ...], str, str], bool] | None = None,
) -> dict[str, Any]:
    """Verify maturity of dated original forecast/actual pairs, not R² alone.

    Each historical pair is rebuilt with the original V3 forecast/materializer
    and original calibration reviewer; generated/source metrics are never
    invented. Independent custody is mandatory before ranking as calibrated.
    """
    if not isinstance(cases, (list, tuple)) or len(cases) > 50:
        raise ValueError("historical calibration case cap 50")
    reviewed = {}
    seen = set()
    for row in cases:
        if not isinstance(row, Mapping):
            raise ValueError("invalid calibration case")
        name = row.get("model_name")
        version = row.get("model_version")
        metric = row.get("metric")
        ref = row.get("prediction_ref")
        key = (name, version, metric)
        if not all(isinstance(v, str) and v for v in (*key, ref)):
            raise ValueError("model identity and prediction_ref required")
        if ref in seen:
            raise ValueError("reused prediction_ref")
        seen.add(ref)
        rows = row.get("observed_daily_values")
        if not isinstance(rows, list) or not 7 <= len(rows) <= 365:
            raise ValueError("original daily observations required")
        if row.get("source_owner") != "empire_os.predictive_registry":
            raise ValueError("calibration source owner invalid")
        if row.get("source_metric") != metric:
            raise ValueError("source metric mismatch")
        if not isinstance(row.get("actual_evidence_ref"), str) or not row["actual_evidence_ref"]:
            raise ValueError("outcome evidence ref required")
        try:
            materialization = materialize_daily_actuals(
                metric=metric, rows=rows, value_field="value",
                date_field="observed_date", horizon_days=row["horizon_days"])
            actual = ForecastActualEvidence(
                metric=metric, observed_date=date.fromisoformat(row["actual_date"]),
                actual_value=row["actual_value"],
                source=row["actual_evidence_ref"],
            )
            evidence = review_forecast_calibration(
                materialization=materialization, actual=actual)
        except (ValueError, TypeError, OverflowError, KeyError):
            raise ValueError("original forecast calibration calculation failed") from None
        # Original reviewer checks forecast target and matching actual date;
        # independent custody is a separate source-owner permission.
        refs = tuple(sorted({r["source"] for r in rows} | {actual.source}))
        try:
            origin = datetime.fromisoformat(row["issued_at"].replace("Z", "+00:00"))
            if origin.tzinfo is None:
                raise ValueError("forecast issue timestamp must be timezone-aware")
            issued_date = origin.astimezone(timezone.utc).date()
            last_input_date = materialization.observations[-1].observed_date
            issue_before_actual = last_input_date <= issued_date < actual.observed_date
            frozen_digest = sha256(json.dumps(
                materialization.as_dict(), sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
            if row.get("original_immutable_forecast_sha256") != frozen_digest:
                raise ValueError("original forecast digest missing or mismatched")
        except (KeyError, TypeError, ValueError):
            raise ValueError("original pre-outcome forecast issue receipt unverified") from None
        independently_custodied = bool(
            evidence.calibration_ready and issue_before_actual
            and verify_original_source is not None
            and verify_original_source(ref, metric, refs, frozen_digest, row["issued_at"]) is True)
        reviewed.setdefault(key, []).append({
            "prediction_ref": ref,
            "original_calibration_ready": evidence.calibration_ready,
            "absolute_error": evidence.absolute_error,
            "predicted": evidence.predicted_value,
            "actual": evidence.actual_value,
            "evidence_refs": list(refs),
            "independent_source_owner_verified": independently_custodied,
        })
    models = []
    for key, items in sorted(reviewed.items()):
        valid = [r for r in items if r["original_calibration_ready"]]
        verified = [r for r in valid if r["independent_source_owner_verified"]]
        threshold = len(verified) >= 3
        mae = round(sum(r["absolute_error"] for r in verified) / len(verified), 4) if verified else None
        models.append({
            "model_name": key[0], "model_version": key[1], "metric": key[2],
            "historical_cases": len(items),
            "out_of_sample_evaluations": len(verified),
            "mean_absolute_error": mae,
            "calibration_evidence_verified": threshold,
            "reason": ("AT_LEAST_THREE_SOURCE_CUSTODIED_OUTCOMES" if threshold
                       else "INSUFFICIENT_INDEPENDENT_SOURCE_CUSTODY_OR_OUTCOMES"),
            "models_not_retrained": True,
        })
    return {
        "schema_version": "empire.microsite.model_calibration_review.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "model_training_authorized": False,
        "source_verifier_attached": verify_original_source is not None,
        "models": models,
        "historical_pairs_checked": len(cases),
        "verified_model_count": sum(m["calibration_evidence_verified"] for m in models),
        "no_live_forecast_mutation": True,
    }
