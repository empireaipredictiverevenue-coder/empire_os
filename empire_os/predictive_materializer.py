"""Canonical daily-actual materializer for Predictive Cloud V3."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from empire_os.predictive_cloud_v3 import (
    DirectionalForecast,
    ObservedMetricPoint,
    forecast_observed_metric,
)


@dataclass(frozen=True)
class ForecastMaterialization:
    metric: str
    observations: tuple[ObservedMetricPoint, ...]
    forecast: DirectionalForecast
    write_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "observations": [
                {
                    "observed_date": point.observed_date.isoformat(),
                    "value": point.value,
                    "source": point.source,
                }
                for point in self.observations
            ],
            "forecast": self.forecast.as_dict(),
            "write_authority": self.write_authority,
        }


def materialize_daily_actuals(
    *,
    metric: str,
    rows: Sequence[Mapping[str, Any]],
    value_field: str,
    date_field: str,
    horizon_days: int,
    forecast_origin_date: date | None = None,
) -> ForecastMaterialization:
    name = str(metric or "").strip()
    if not name:
        raise ValueError("metric required")
    if not value_field or not date_field:
        raise ValueError("value_field and date_field required")

    by_date: dict[date, ObservedMetricPoint] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("canonical actual row must be a mapping")
        if row.get(value_field) is None or row.get(date_field) is None:
            raise ValueError("canonical actual row missing required fields")
        source = str(row.get("source") or "").strip()
        if not source:
            raise ValueError("canonical actual row requires source provenance")

        observed_date = date.fromisoformat(str(row[date_field]))
        value = float(row[value_field])
        if value < 0:
            raise ValueError("canonical actual values must be nonnegative")

        point = ObservedMetricPoint(
            observed_date=observed_date,
            value=value,
            source=source,
        )
        existing = by_date.get(observed_date)
        if existing and existing.value != point.value:
            raise ValueError("conflicting canonical actuals for observed date")
        by_date[observed_date] = point

    observations = tuple(by_date[key] for key in sorted(by_date))
    forecast = forecast_observed_metric(
        metric=name,
        points=observations,
        horizon_days=horizon_days,
        forecast_origin_date=forecast_origin_date,
    )
    return ForecastMaterialization(
        metric=name,
        observations=observations,
        forecast=forecast,
    )


def produce_native_revenue_forecast(
    *, tenant_id: str, census_dsn: str, reader_dsn: str,
    writer_dsn: str = "", registration_enabled: bool = False,
    history_days: int = 7, horizon_days: int = 7,
    connect_factory=None,
) -> dict[str, Any]:
    """Private scheduled workflow, using only original authenticated readers.

    No HTTP/request points or runtime JSON observations are accepted. REV077
    positive daily source snapshots are provisional model inputs, NOT a proof
    of upstream ledger completeness or financially final customer outcomes.
    Unknown/empty days stop the forecast; never interpolate or impute zero.
    Registration preserves all REV078 unverified source/finality flags.
    """
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal, ROUND_HALF_UP
    from hashlib import md5, sha256
    import json
    import math
    from pathlib import Path
    from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
    from empire_os.predictive_revenue_tenant_registry_inspector import (
        _uuid, read_native_forecast_registration,
    )
    from empire_os.predictive_registry_transport import (
        EmpireDbProspectiveForecastRegistration,
    )

    now = datetime.now(timezone.utc)
    result = {
        "schema_version": "empire.predictive_revenue.native_producer.v1",
        "observed_at": now.isoformat(),
        "status": "NATIVE_SOURCE_CONFIGURATION_HOLD",
        "authenticated_source_days": 0,
        "source_reader_called": False,
        "model_called": False,
        "registration_attempted": False,
        "registration_write_committed": False,
        "registration_commit_state": "NOT_ATTEMPTED",
        "independent_registry_readback_verified": False,
        "source_snapshot_authenticated": False,
        "source_census_complete_as_of_snapshot": False,
        "financial_actuals_verified": False,
        "calibration_authorized": False,
        "customer_release_authorized": False,
        "customer_data_disclosed": False,
        "outbound": False,
    }
    try:
        tenant = _uuid(tenant_id)
        if (type(history_days) is not int or not 7 <= history_days <= 120
                or type(horizon_days) is not int or not 1 <= horizon_days <= 365
                or type(registration_enabled) is not bool
                or not census_dsn or not reader_dsn):
            return result
        rows = []
        source_days = []
        # All observations precede today's issuance. Every calendar day is
        # queried; positive event coverage is never inferred across gaps.
        for offset in range(history_days, 0, -1):
            day = now.date() - timedelta(days=offset)
            result["source_reader_called"] = True
            result["status"] = "AUTHENTICATED_SOURCE_READ_FAILED"
            census = read_daily_revenue_census(
                day_utc=day, tenant_id=tenant, as_of=now, dsn=census_dsn,
                connect_factory=connect_factory, require_session_tenant_binding=True,
            )
            if (census.get("database_session_tenant_identity_matched") is not True
                    or census.get("observed_utc_date") != day.isoformat()):
                return result
            result["authenticated_source_days"] += 1
            if census.get("status") != "DAY_SOURCE_CENSUS_CANDIDATE":
                result["status"] = "AUTHENTICATED_SOURCE_DAY_EMPTY_OR_INCOMPLETE"
                result["first_rejected_source_day"] = day.isoformat()
                return result
            value = census.get("tenant_candidate_amount_cents")
            if (type(value) is not int or not 0 < value <= 1_000_000_000_000
                    or census.get("source_scoped_internal_consistency_candidate") is not True
                    or census.get("eligible_for_revenue_forecast_calibration") is not False):
                result["status"] = "SOURCE_DAY_VALUE_OR_PROVENANCE_REJECTED"
                return result
            rows.append({"observed_date": day.isoformat(), "value": value,
                         "source": "canonical:commercial_events:rev077"})
            source_days.append({"day": day.isoformat(), "cents": value,
                                "event_count": census["tenant_event_count"]})
        result["source_snapshot_authenticated"] = True
        result["source_financial_finality"] = "UNVERIFIED_CANDIDATE_INPUTS_ONLY"
        result["model_called"] = True
        result["status"] = "ORIGINAL_MODEL_INPUT_OR_OUTPUT_REJECTED"
        materialization = materialize_daily_actuals(
            metric="recognized_revenue_cents", rows=rows, value_field="value",
            date_field="observed_date", horizon_days=horizon_days,
            forecast_origin_date=now.date(),
        )
        forecast = materialization.forecast
        if (not forecast.available or forecast.predicted_value is None
                or not math.isfinite(forecast.predicted_value)):
            return result
        prediction = int(Decimal(str(forecast.predicted_value)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))
        model_name = "empire-directional-linear"
        model_version = "v3-registration-day-v1"
        model_path = Path(__file__).with_name("predictive_cloud_v3.py")
        model_digest = sha256(model_path.read_bytes()).hexdigest()
        # Deterministic original inputs, not changing query timestamps.
        digest = sha256(json.dumps({
            "tenant": tenant, "source": "REV077",
            "metric": materialization.metric, "days": source_days,
            "model_name": model_name, "model_version": model_version,
            "model_code_sha256": model_digest,
            "origin_utc_day": now.date().isoformat(),
            "horizon_days": horizon_days,
        }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        target = now.date() + timedelta(days=horizon_days)
        ref = "efr:" + md5((tenant + ":" + model_name + ":" + model_version
                           + ":" + target.isoformat() + ":" + str(horizon_days)).encode(),
                          usedforsecurity=False).hexdigest()
        result.update(model_name=model_name, model_version=model_version,
                      model_code_sha256=model_digest, source_evidence_sha256=digest,
                      target_utc_date=target.isoformat(), horizon_days=horizon_days)
        expected = dict(model_name=model_name, model_version=model_version,
                        horizon_days=horizon_days, sample_count=history_days,
                        predicted_cents=prediction, r_squared=forecast.r_squared,
                        evidence_confidence=forecast.evidence_confidence,
                        direction=forecast.direction)

        def readback():
            return read_native_forecast_registration(
                dsn=reader_dsn, tenant_id=tenant, registration_ref=ref,
                connect_factory=connect_factory)

        def matches(stored):
            evidence = stored.get("evidence")
            return (stored.get("found") is True
                    and all(stored.get(k) == v for k, v in expected.items()
                            if k not in ("r_squared", "evidence_confidence"))
                    and all(Decimal(str(stored.get(k))) == Decimal(str(expected[k]))
                            for k in ("r_squared", "evidence_confidence"))
                    and isinstance(evidence, dict)
                    and evidence.get("source_evidence_sha256") == digest
                    and evidence.get("target_utc_date") == target.isoformat()
                    and evidence.get("observed_through_utc") == rows[-1]["observed_date"]
                    and evidence.get("horizon_basis") == "registration_utc_day"
                    and evidence.get("db_registration_clock") is True
                    and evidence.get("original_source_authentication") is False
                    and evidence.get("independent_financial_actuals") is False
                    and evidence.get("calibration_authorized") is False
                    and stored["registered_at"].date() == now.date())

        result["status"] = "NATIVE_REGISTRY_READER_UNAVAILABLE"
        existing = readback()  # Always before attempting a write.
        if existing["found"]:
            result["status"] = ("EXISTING_NATIVE_FORECAST_VERIFIED" if matches(existing)
                                else "IMMUTABLE_FORECAST_INPUT_CONFLICT_HOLD")
            result["independent_registry_readback_verified"] = matches(existing)
            return result
        if not registration_enabled or not writer_dsn:
            result["status"] = "NATIVE_WRITER_ACTIVATION_REQUIRED"
            return result
        if datetime.now(timezone.utc).date() != now.date():
            result["status"] = "UTC_ISSUANCE_DAY_CHANGED_RETRY_NEXT_CYCLE"
            return result
        result["status"] = "NATIVE_REGISTRATION_FAILED_COMMIT_UNKNOWN"
        result["registration_attempted"] = True
        result["registration_commit_state"] = "UNKNOWN"
        try:
            receipt = EmpireDbProspectiveForecastRegistration(
                writer_dsn, enabled=True, connect_factory=connect_factory,
                forbidden_session_users=(existing["reader_session_user"],),
            ).register(tenant_id=tenant, **expected,
                       observed_through=date.fromisoformat(rows[-1]["observed_date"]),
                       source_evidence_sha256=digest)
            result["registration_write_committed"] = receipt["registration_write_committed"]
            result["registration_commit_state"] = "COMMITTED"
            if receipt["registration_ref"] != ref:
                result["status"] = "REGISTRATION_CLOCK_OR_REFERENCE_MISMATCH_HOLD"
                return result
        except Exception:
            # Concurrent duplicate or commit acknowledgement loss: read only,
            # never overwrite, generate another key, or retry a write.
            pass
        result["status"] = "REGISTRATION_COMMIT_UNKNOWN_READBACK_FAILED"
        stored = readback()
        if matches(stored):
            result["status"] = "NATIVE_FORECAST_REGISTERED_AND_READ_BACK"
            result["registration_commit_state"] = "EXACT_RECORD_PRESENT"
            result["registration_ref"] = ref
            result["independent_registry_readback_verified"] = True
        else:
            result["status"] = "NATIVE_REGISTRATION_NOT_VERIFIED_HOLD"
        return result
    except Exception:
        # Stages above preserve the failure boundary without credentials,
        # SQL text, customer values or an invented successful registration.
        return result
