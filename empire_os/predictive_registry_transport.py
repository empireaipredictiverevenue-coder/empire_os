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


# Native EmpireDB REV078 transport. The older V3 public RPC above is kept
# unactivated and unchanged for historical contract compatibility. In
# particular, never connect public /forecast/register caller-supplied points
# to this restricted tenant-bound capability.
NATIVE_FORECAST_REGISTRAR_ROLE = 'empire_predictive_forecast_registrar'
NATIVE_FORECAST_REGISTER_SQL = (
    'SELECT registration_ref,registered_at '
    'FROM public.register_predictive_revenue_forecast_v1('
    '%s::text,%s::text,%s::date,%s::integer,%s::integer,%s::numeric,'
    '%s::numeric,%s::numeric,%s::text,%s::text)'
)


class EmpireDbProspectiveForecastRegistration:
    """Private first-party REV078 registration, disabled unless explicitly enabled.

    A successful registry insert never validates caller-supplied observations,
    settlement, calibration, external timestamp custody or customer permission.
    The trusted tenant is bound by the PostgreSQL session_user, not inputs.
    """

    def __init__(self, dsn: str, *, enabled: bool = False,
                 connect_factory: Callable | None = None):
        if type(enabled) is not bool or not enabled:
            raise PredictiveRegistryTransportError(
                'native forecast registration not authorised')
        if type(dsn) is not str or not dsn.strip():
            raise PredictiveRegistryTransportError(
                'dedicated native registrar credential required')
        self._dsn = dsn
        if connect_factory is None:
            try:
                import psycopg
            except ImportError:
                raise PredictiveRegistryTransportError(
                    'native PostgreSQL driver unavailable') from None
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def register(self, *, tenant_id: str, model_name: str,
                 model_version: str, observed_through: 'date',
                 horizon_days: int, sample_count: int, predicted_cents: int,
                 r_squared: float, evidence_confidence: float,
                 direction: str, source_evidence_sha256: str) -> dict[str, Any]:
        import math
        import re
        from datetime import date, datetime, timezone, timedelta
        from uuid import UUID

        try:
            if type(tenant_id) is not str or str(UUID(tenant_id)) != tenant_id:
                raise ValueError('canonical tenant required')
            if (type(observed_through) is not date
                or type(horizon_days) is not int or not 1 <= horizon_days <= 365
                or type(sample_count) is not int or not 7 <= sample_count <= 120
                or type(predicted_cents) is not int
                or not 0 <= predicted_cents <= 1_000_000_000_000_000):
                raise ValueError('bounded forecast values required')
            if (type(model_name) is not str or type(model_version) is not str
                or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',model_name)
                or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',model_version)
                or type(direction) is not str
                or direction not in ('up','down','flat')):
                raise ValueError('bounded forecast metadata required')
            if (type(r_squared) not in (float,int)
                or type(evidence_confidence) not in (float,int)
                or not math.isfinite(r_squared)
                or not math.isfinite(evidence_confidence)
                or not 0 <= r_squared <= 1
                or not 0 <= evidence_confidence <= 1
                or type(source_evidence_sha256) is not str
                or not re.fullmatch('[0-9a-f]{64}',source_evidence_sha256)):
                raise ValueError('source fingerprint or model score invalid')
        except (TypeError, ValueError, AttributeError):
            raise PredictiveRegistryTransportError(
                'native prospective forecast input invalid') from None

        args = (model_name, model_version, observed_through, horizon_days,
                sample_count, predicted_cents, r_squared,
                evidence_confidence, direction, source_evidence_sha256)
        try:
            with self._connect(self._dsn, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SET LOCAL statement_timeout = \'4000ms\'')
                    cursor.execute('SELECT current_database()')
                    if cursor.fetchone() != ('empiredb',):
                        raise ValueError('not canonical database')
                    cursor.execute('SET LOCAL ROLE ' + NATIVE_FORECAST_REGISTRAR_ROLE)
                    cursor.execute('SELECT public.empire_current_tenant_id()')
                    binding = cursor.fetchone()
                    if (type(binding) not in (tuple,list) or len(binding)!=1
                        or str(binding[0]) != tenant_id):
                        raise ValueError('database tenant binding mismatch')
                    cursor.execute(NATIVE_FORECAST_REGISTER_SQL,args)
                    row = cursor.fetchone()
                    if type(row) not in (tuple,list) or len(row)!=2:
                        raise ValueError('invalid registration receipt')
                    ref, when = row
                    if (type(ref) is not str or not re.fullmatch('efr:[0-9a-f]{32}',ref)
                        or type(when) is not datetime or when.utcoffset() is None):
                        raise ValueError('invalid trusted registration receipt')
                    utc_when = when.astimezone(timezone.utc)
                    now = datetime.now(timezone.utc)
                    if utc_when > now+timedelta(seconds=5) or utc_when < now-timedelta(seconds=60):
                        raise ValueError('registered timestamp outside live read window')
        except Exception:
            raise PredictiveRegistryTransportError(
                'native tenant-bound registration unavailable') from None
        return {
            'schema_version':'empire.predictive_revenue.native_registration_receipt.v1',
            'status':'DB_REGISTERED_SOURCE_EVIDENCE_UNVERIFIED',
            'registration_ref':ref,
            'registered_at_utc':utc_when.isoformat(),
            'database_tenant_session_matched':True,
            'registration_write_committed':True,
            'original_source_authenticated':False,
            'independent_timestamp_custody_verified':False,
            'financial_actuals_verified':False,
            'calibration_authorized':False,
            'commercial_execution':False,
            'customer_data_disclosed':False,
            'execution_authority':'PRIVATE_SCOPED_FORECAST_REGISTRATION_ONLY',
        }
