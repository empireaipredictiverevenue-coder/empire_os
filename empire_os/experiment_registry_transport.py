"""Dedicated Phase 11 experiment registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.experiment_registry import ExperimentRegistryRecord


class ExperimentRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_experiment_registry"
ROLE = "empire_experiment_registry_writer"
SQL = (
    "select public.record_experiment_registry("
    "%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_experiment_key",
    "p_hypothesis",
    "p_metric",
    "p_control_variant",
    "p_treatment_variants",
    "p_assignment_integrity_verified",
    "p_exposure_integrity_verified",
    "p_outcome_window_closed",
    "p_evidence",
)


class PostgresExperimentRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise ExperimentRegistryTransportError(
                "dedicated experiment registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise ExperimentRegistryTransportError(
                    "psycopg is required for experiment registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise ExperimentRegistryTransportError(
                "experiment registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise ExperimentRegistryTransportError(
                "unexpected experiment registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {"p_treatment_variants", "p_evidence"}:
                value = json.dumps(
                    value or ([] if key == "p_treatment_variants" else {}),
                    separators=(",", ":"),
                    sort_keys=True,
                )
            values.append(value)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute(SQL, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise ExperimentRegistryTransportError(
                "experiment registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise ExperimentRegistryTransportError(
                "experiment registry RPC returned no result"
            )
        return row[0]


class RpcExperimentRegistryRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def record(self, item: ExperimentRegistryRecord):
        item.validate()
        result = self.rpc(
            RPC_NAME,
            {
                "p_experiment_key": item.experiment_key,
                "p_hypothesis": item.hypothesis,
                "p_metric": item.metric,
                "p_control_variant": item.control_variant,
                "p_treatment_variants": list(item.treatment_variants),
                "p_assignment_integrity_verified": (
                    item.assignment_integrity_verified
                ),
                "p_exposure_integrity_verified": (
                    item.exposure_integrity_verified
                ),
                "p_outcome_window_closed": item.outcome_window_closed,
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise ExperimentRegistryTransportError(
                "experiment registry RPC returned invalid payload"
            )
        return result
