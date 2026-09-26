"""Least-privilege PostgreSQL transport for Phase 3F outcome/revenue roles."""
from __future__ import annotations

import json
from typing import Any, Callable


class OutcomeTransportError(RuntimeError):
    pass


ROLE_FUNCTIONS = {
    "empire_astra_observer": {
        "get_commercial_outcome_feedback": (
            "select public.get_commercial_outcome_feedback(%s)",
            ("p_limit",),
        ),
        "get_astra_operational_evidence": (
            "select public.get_astra_operational_evidence()",
            (),
        ),
    },
    "empire_outcome_recorder": {
        "record_commercial_outcome": (
            "select public.record_commercial_outcome(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
            (
                "p_fulfilment_order_id", "p_delivery_outcome",
                "p_conversion_outcome", "p_buyer_satisfaction",
                "p_evidence_kind", "p_evidence_reference", "p_evidence",
                "p_idempotency_key", "p_actor",
            ),
        ),
    },
    "empire_revenue_recognizer": {
        "list_revenue_recognition_work": (
            "select public.list_revenue_recognition_work(%s)",
            ("p_limit",),
        ),
        "recognize_bsc_revenue": (
            "select public.recognize_bsc_revenue(%s,%s)",
            ("p_fulfilment_order_id", "p_actor"),
        ),
    },
    "empire_outcome_reader": {
        "get_commercial_outcome_feedback": (
            "select public.get_commercial_outcome_feedback(%s)",
            ("p_limit",),
        ),
        "get_phase3f_commercial_scorecard": (
            "select public.get_phase3f_commercial_scorecard(%s)",
            ("p_days",),
        ),
    },
}


class PostgresOutcomeRpc:
    def __init__(
        self,
        dsn: str,
        role: str,
        *,
        connect_factory: Callable | None = None,
    ):
        self.dsn = str(dsn or "").strip()
        self.role = str(role or "").strip()
        if not self.dsn:
            raise OutcomeTransportError("dedicated outcome database DSN required")
        if self.role not in ROLE_FUNCTIONS:
            raise OutcomeTransportError("unsupported outcome database role")
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise OutcomeTransportError(
                    "psycopg is required for outcome role transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        allowed = ROLE_FUNCTIONS[self.role]
        if name not in allowed:
            raise OutcomeTransportError(
                f"{self.role} is not allowed to execute {name}"
            )
        sql, keys = allowed[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise OutcomeTransportError("unexpected outcome RPC parameters")

        values = []
        for key in keys:
            value = params[key]
            if key == "p_evidence":
                value = json.dumps(
                    value or {}, separators=(",", ":"), sort_keys=True
                )
            values.append(value)

        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + self.role)
                    cursor.execute(sql, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise OutcomeTransportError(
                "dedicated outcome database RPC failed"
            ) from exc

        if not row or len(row) != 1:
            raise OutcomeTransportError(
                "dedicated outcome database RPC returned no result"
            )
        return row[0]
