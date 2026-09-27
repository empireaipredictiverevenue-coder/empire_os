"""Dedicated Predictive Cloud V3 forecast registry transports."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.predictive_registry import ForecastRegistryRecord


class PredictiveRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_predictive_forecast"
WRITER_ROLE = "empire_predictive_registry_writer"
READER_ROLE = "empire_predictive_registry_reader"
WRITE_SQL = (
    "select public.record_predictive_forecast("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_forecast_key",
    "p_model_name",
    "p_model_version",
    "p_metric",
    "p_dimension_key",
    "p_horizon_days",
    "p_sample_count",
    "p_latest_observed_value",
    "p_predicted_value",
    "p_daily_slope",
    "p_r_squared",
    "p_evidence_confidence",
    "p_direction",
    "p_evidence",
)
READ_SQL = """
SELECT
  id,
  forecast_key,
  model_name,
  model_version,
  metric,
  dimension_key,
  horizon_days,
  sample_count,
  latest_observed_value,
  predicted_value,
  daily_slope,
  r_squared,
  evidence_confidence,
  direction,
  source,
  evidence,
  generated_at
FROM public.predictive_forecasts
WHERE forecast_key IS NOT NULL
ORDER BY generated_at DESC,id DESC
LIMIT %s
"""


class PostgresPredictiveRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise PredictiveRegistryTransportError(
                "dedicated predictive registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise PredictiveRegistryTransportError(
                    "psycopg is required for predictive registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise PredictiveRegistryTransportError(
                "predictive registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise PredictiveRegistryTransportError(
                "unexpected predictive registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key == "p_evidence":
                value = json.dumps(
                    value or {},
                    separators=(",", ":"),
                    sort_keys=True,
                )
            values.append(value)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + WRITER_ROLE)
                    cursor.execute(WRITE_SQL, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise PredictiveRegistryTransportError(
                "predictive registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise PredictiveRegistryTransportError(
                "predictive registry RPC returned no result"
            )
        return row[0]


class PostgresPredictiveRegistryReader:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise PredictiveRegistryTransportError(
                "dedicated predictive registry read DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise PredictiveRegistryTransportError(
                    "psycopg is required for predictive registry read"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, *, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + READER_ROLE)
                    cursor.execute(READ_SQL, (bounded,))
                    rows = cursor.fetchall()
                    columns = [desc.name for desc in cursor.description]
        except Exception as exc:
            raise PredictiveRegistryTransportError(
                "predictive registry read failed"
            ) from exc
        return [
            dict(zip(columns, row))
            for row in rows
        ]


class RpcPredictiveRegistryRepository:
    def __init__(
        self,
        rpc: Callable[[str, dict[str, Any]], Any],
        *,
        reader: Callable[..., list[dict[str, Any]]] | None = None,
    ):
        self.rpc = rpc
        self.reader = reader

    def record(self, item: ForecastRegistryRecord):
        item.validate()
        f = item.forecast
        result = self.rpc(
            RPC_NAME,
            {
                "p_forecast_key": item.forecast_key,
                "p_model_name": item.model_name,
                "p_model_version": item.model_version,
                "p_metric": f.metric,
                "p_dimension_key": item.dimension_key,
                "p_horizon_days": f.horizon_days,
                "p_sample_count": f.sample_count,
                "p_latest_observed_value": f.latest_observed_value,
                "p_predicted_value": f.predicted_value,
                "p_daily_slope": f.daily_slope,
                "p_r_squared": f.r_squared,
                "p_evidence_confidence": f.evidence_confidence,
                "p_direction": f.direction,
                "p_evidence": {
                    **dict(item.evidence),
                    "registry_payload_sha256": item.payload_sha256,
                },
            },
        )
        if not isinstance(result, dict):
            raise PredictiveRegistryTransportError(
                "predictive registry RPC returned invalid payload"
            )
        return result

    def list_forecasts(self, *, limit: int):
        if self.reader is None:
            raise PredictiveRegistryTransportError(
                "predictive registry reader not activated"
            )
        rows = self.reader(limit=limit)
        if not isinstance(rows, list):
            raise PredictiveRegistryTransportError(
                "predictive registry reader returned invalid payload"
            )
        return rows
