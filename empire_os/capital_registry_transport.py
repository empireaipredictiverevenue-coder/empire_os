"""Dedicated Phase 15 capital review registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.capital_registry import CapitalReviewRecord


class CapitalRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_capital_review"
ROLE = "empire_capital_registry_writer"
SQL = (
    "select public.record_capital_review("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)"
)
PARAM_KEYS = (
    "p_review_key",
    "p_candidate_id",
    "p_expected_return_cents",
    "p_required_capital_cents",
    "p_downside_loss_cents",
    "p_confidence",
    "p_time_to_revenue_days",
    "p_risk_adjusted_score",
    "p_review_eligible",
    "p_minimum_confidence",
    "p_maximum_downside_ratio",
    "p_blockers",
    "p_evidence",
)


class PostgresCapitalRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise CapitalRegistryTransportError(
                "dedicated capital registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise CapitalRegistryTransportError(
                    "psycopg is required for capital registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise CapitalRegistryTransportError(
                "capital registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise CapitalRegistryTransportError(
                "unexpected capital registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {"p_blockers", "p_evidence"}:
                value = json.dumps(
                    value or ([] if key == "p_blockers" else {}),
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
            raise CapitalRegistryTransportError(
                "capital registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise CapitalRegistryTransportError(
                "capital registry RPC returned no result"
            )
        return row[0]


class RpcCapitalRegistryRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def record(self, item: CapitalReviewRecord):
        item.validate()
        c = item.candidate
        p = item.policy
        r = item.review
        result = self.rpc(
            RPC_NAME,
            {
                "p_review_key": item.review_key,
                "p_candidate_id": c.candidate_id,
                "p_expected_return_cents": c.expected_return_cents,
                "p_required_capital_cents": c.required_capital_cents,
                "p_downside_loss_cents": c.downside_loss_cents,
                "p_confidence": c.confidence,
                "p_time_to_revenue_days": c.time_to_revenue_days,
                "p_risk_adjusted_score": r.assessment.risk_adjusted_score,
                "p_review_eligible": r.review_eligible,
                "p_minimum_confidence": p.minimum_confidence,
                "p_maximum_downside_ratio": p.maximum_downside_ratio,
                "p_blockers": list(r.blockers),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise CapitalRegistryTransportError(
                "capital registry RPC returned invalid payload"
            )
        return result
