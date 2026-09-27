"""Dedicated Phase 11 causal conclusion registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.experiment_conclusion import ExperimentConclusionRecord


class ExperimentConclusionTransportError(RuntimeError):
    pass


RPC_NAME = "record_experiment_causal_conclusion"
WRITER_ROLE = "empire_experiment_conclusion_writer"
READER_ROLE = "empire_experiment_conclusion_reader"
SQL = (
    "select public.record_experiment_causal_conclusion("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_conclusion_key",
    "p_experiment_key",
    "p_metric",
    "p_control_count",
    "p_treatment_count",
    "p_control_mean",
    "p_treatment_mean",
    "p_assignment_integrity_verified",
    "p_exposure_integrity_verified",
    "p_outcome_window_closed",
    "p_evidence_refs",
    "p_evidence",
)


class PostgresExperimentConclusionRpc:
    def __init__(self, dsn: str, *, connect_factory: Callable | None = None):
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise ExperimentConclusionTransportError(
                "dedicated experiment conclusion DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise ExperimentConclusionTransportError(
                    "psycopg is required for experiment conclusion registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise ExperimentConclusionTransportError(
                "experiment conclusion role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise ExperimentConclusionTransportError(
                "unexpected experiment conclusion RPC parameters"
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
                    cursor.execute(SQL, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise ExperimentConclusionTransportError(
                "experiment conclusion RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise ExperimentConclusionTransportError(
                "experiment conclusion RPC returned no result"
            )
        return row[0]


READ_SQL = """
SELECT
  id,
  conclusion_key,
  experiment_key,
  metric,
  control_count,
  treatment_count,
  control_mean,
  treatment_mean,
  absolute_lift,
  relative_lift,
  effect_direction,
  assignment_integrity_verified,
  exposure_integrity_verified,
  outcome_window_closed,
  causal_review_eligible,
  statistical_significance_available,
  evidence_refs,
  evidence,
  execution_authority,
  traffic_mutation,
  rollout_enabled,
  pricing_mutation,
  created_at
FROM public.experiment_causal_conclusions
ORDER BY created_at DESC,id DESC
LIMIT %s
"""


class PostgresExperimentConclusionReader:
    def __init__(self, dsn: str, *, connect_factory: Callable | None = None):
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise ExperimentConclusionTransportError(
                "dedicated experiment conclusion read DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise ExperimentConclusionTransportError(
                    "psycopg is required for experiment conclusion read"
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
                    columns = [
                        description.name
                        for description in cursor.description
                    ]
                    rows = cursor.fetchall()
        except Exception as exc:
            raise ExperimentConclusionTransportError(
                "experiment conclusion read failed"
            ) from exc
        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]


class RpcExperimentConclusionRepository:
    def __init__(
        self,
        rpc: Callable[[str, dict[str, Any]], Any],
        *,
        reader: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        self.rpc = rpc
        self.reader = reader

    def record_conclusion(self, item: ExperimentConclusionRecord):
        item.validate()
        c = item.conclusion
        result = self.rpc(
            RPC_NAME,
            {
                "p_conclusion_key": c.conclusion_key,
                "p_experiment_key": c.experiment_key,
                "p_metric": c.metric,
                "p_control_count": c.control_count,
                "p_treatment_count": c.treatment_count,
                "p_control_mean": c.control_mean,
                "p_treatment_mean": c.treatment_mean,
                "p_assignment_integrity_verified": (
                    c.assignment_integrity_verified
                ),
                "p_exposure_integrity_verified": (
                    c.exposure_integrity_verified
                ),
                "p_outcome_window_closed": c.outcome_window_closed,
                "p_evidence_refs": list(c.evidence_refs),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise ExperimentConclusionTransportError(
                "experiment conclusion RPC returned invalid payload"
            )
        return result

    def list_conclusions(self, *, limit: int):
        if self.reader is None:
            raise ExperimentConclusionTransportError(
                "experiment conclusion reader not activated"
            )
        rows = self.reader(limit=limit)
        if not isinstance(rows, list):
            raise ExperimentConclusionTransportError(
                "experiment conclusion reader returned invalid payload"
            )
        return rows
