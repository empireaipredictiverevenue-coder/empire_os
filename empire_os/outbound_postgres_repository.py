"""Least-privilege EmpireDB repository for outbound deliverability evidence."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence


class DeliverabilityRepositoryError(RuntimeError):
    pass


READ_ROLE = "empire_outbound_deliverability_reader"
WRITE_ROLE = "empire_outbound_deliverability_writer"


def _bounded_limit(value: int, *, maximum: int = 500) -> int:
    parsed = int(value)
    if parsed < 1:
        raise ValueError("limit_must_be_positive")
    return min(parsed, maximum)


class PostgresDeliverabilityRepository:
    """Tenant-scoped read model for persisted Ringleader evidence."""

    def __init__(
        self,
        dsn: str,
        scope_key: str,
        *,
        connect_factory: Callable | None = None,
        read_role: str = READ_ROLE,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        self.scope_key = str(scope_key or "").strip()
        self.read_role = str(read_role or "").strip()
        if not self.dsn:
            raise DeliverabilityRepositoryError(
                "dedicated deliverability reader DSN required"
            )
        if not self.scope_key:
            raise DeliverabilityRepositoryError("scope_key required")
        if not self.read_role:
            raise DeliverabilityRepositoryError("read_role required")

        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DeliverabilityRepositoryError(
                    "psycopg is required for EmpireDB deliverability transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    @staticmethod
    def _row_dict(cursor, row) -> dict[str, Any]:
        names = [
            column.name if hasattr(column, "name") else column[0]
            for column in cursor.description
        ]
        return dict(zip(names, row))

    def _read(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(f"SET LOCAL ROLE {self.read_role}")
                    cursor.execute(
                        "SELECT set_config('app.scope_key', %s, true)",
                        (self.scope_key,),
                    )
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    return [self._row_dict(cursor, row) for row in rows]
        except Exception as exc:
            raise DeliverabilityRepositoryError(
                "EmpireDB deliverability read failed"
            ) from exc

    def observations(self, *, limit: int = 200) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              id,scope_key,observed_at,source,domain,mailbox_key,
              transport_key,recipient_mx,metric_name,metric_value,
              unit,evidence,evidence_hash,previous_evidence_hash,created_at
            FROM public.outbound_deliverability_observations
            WHERE scope_key = %s
            ORDER BY observed_at DESC,id
            LIMIT %s
            """,
            (self.scope_key, _bounded_limit(limit)),
        )

    def decisions(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              id,scope_key,decision_key,observed_at,posture,
              domain,mailbox_key,transport_key,recipient_mx,
              hard_holds,tasks,evidence,mutation_authorized,
              evidence_hash,previous_evidence_hash,created_at
            FROM public.outbound_ringleader_decisions
            WHERE scope_key = %s
            ORDER BY observed_at DESC,id
            LIMIT %s
            """,
            (self.scope_key, _bounded_limit(limit)),
        )

    def pool_history(
        self,
        pool_key: str,
        *,
        limit: int = 100,
    ) -> Sequence[Mapping[str, Any]]:
        key = str(pool_key or "").strip()
        if not key:
            raise ValueError("pool_key_required")
        return self._read(
            """
            SELECT
              id,scope_key,pool_key,pool_kind,state,daily_cap,
              reputation_credit,evidence,observed_at,created_at
            FROM public.outbound_sender_pool_observations
            WHERE scope_key = %s
              AND pool_key = %s
            ORDER BY observed_at DESC,id
            LIMIT %s
            """,
            (self.scope_key, key, _bounded_limit(limit)),
        )

    def contact_pressure(
        self,
        *,
        person_key: str,
        company_key: str,
        limit: int = 100,
    ) -> Sequence[Mapping[str, Any]]:
        person = str(person_key or "").strip()
        company = str(company_key or "").strip()
        if not person or not company:
            raise ValueError("person_and_company_keys_required")
        return self._read(
            """
            SELECT
              id,scope_key,person_key,company_key,campaign_key,
              agent_key,channel,occurred_at,evidence,created_at
            FROM public.outbound_contact_pressure_events
            WHERE scope_key = %s
              AND (person_key = %s OR company_key = %s)
            ORDER BY occurred_at DESC,id
            LIMIT %s
            """,
            (
                self.scope_key,
                person,
                company,
                _bounded_limit(limit),
            ),
        )


class PostgresDeliverabilityEvidenceWriter:
    """Append-only writer. No update/delete surfaces are exposed."""

    def __init__(
        self,
        dsn: str,
        scope_key: str,
        *,
        connect_factory: Callable | None = None,
        write_role: str = WRITE_ROLE,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        self.scope_key = str(scope_key or "").strip()
        self.write_role = str(write_role or "").strip()
        if not self.dsn:
            raise DeliverabilityRepositoryError(
                "dedicated deliverability writer DSN required"
            )
        if not self.scope_key:
            raise DeliverabilityRepositoryError("scope_key required")
        if not self.write_role:
            raise DeliverabilityRepositoryError("write_role required")

        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DeliverabilityRepositoryError(
                    "psycopg is required for EmpireDB deliverability transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def _insert(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> Mapping[str, Any]:
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {self.write_role}")
                    cursor.execute(
                        "SELECT set_config('app.scope_key', %s, true)",
                        (self.scope_key,),
                    )
                    cursor.execute(sql, params)
                    row = cursor.fetchone()
                    if not row:
                        raise DeliverabilityRepositoryError(
                            "EmpireDB append returned no row"
                        )
                    connection.commit()
                    return {"id": str(row[0])}
        except DeliverabilityRepositoryError:
            raise
        except Exception as exc:
            raise DeliverabilityRepositoryError(
                "EmpireDB deliverability append failed"
            ) from exc

    def append_observation(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        observed_at = row.get("observed_at") or datetime.now(timezone.utc)
        return self._insert(
            """
            INSERT INTO public.outbound_deliverability_observations(
              scope_key,observed_at,source,domain,mailbox_key,
              transport_key,recipient_mx,metric_name,metric_value,
              unit,evidence,evidence_hash,previous_evidence_hash
            ) VALUES(
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s
            )
            RETURNING id
            """,
            (
                self.scope_key,
                observed_at,
                str(row.get("source") or ""),
                row.get("domain"),
                row.get("mailbox_key"),
                row.get("transport_key"),
                row.get("recipient_mx"),
                str(row.get("metric_name") or ""),
                row.get("metric_value"),
                str(row.get("unit") or "count"),
                json.dumps(dict(row.get("evidence") or {}), sort_keys=True, default=str),
                row.get("evidence_hash"),
                row.get("previous_evidence_hash"),
            ),
        )

    def append_decision(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        if row.get("mutation_authorized") is not False:
            raise DeliverabilityRepositoryError(
                "ringleader_persistence_requires_mutation_authorized_false"
            )
        return self._insert(
            """
            INSERT INTO public.outbound_ringleader_decisions(
              scope_key,decision_key,observed_at,posture,
              domain,mailbox_key,transport_key,recipient_mx,
              hard_holds,tasks,evidence,mutation_authorized,
              evidence_hash,previous_evidence_hash
            ) VALUES(
              %s,%s,%s,%s,%s,%s,%s,%s,
              %s::jsonb,%s::jsonb,%s::jsonb,FALSE,%s,%s
            )
            ON CONFLICT(scope_key,decision_key) DO NOTHING
            RETURNING id
            """,
            (
                self.scope_key,
                str(row.get("decision_key") or ""),
                row.get("observed_at") or datetime.now(timezone.utc),
                str(row.get("posture") or "OBSERVE"),
                row.get("domain"),
                row.get("mailbox_key"),
                row.get("transport_key"),
                row.get("recipient_mx"),
                json.dumps(list(row.get("hard_holds") or []), sort_keys=True, default=str),
                json.dumps(list(row.get("tasks") or []), sort_keys=True, default=str),
                json.dumps(dict(row.get("evidence") or {}), sort_keys=True, default=str),
                row.get("evidence_hash"),
                row.get("previous_evidence_hash"),
            ),
        )


def configured_deliverability_repository_from_env(
    *,
    connect_factory: Callable | None = None,
) -> PostgresDeliverabilityRepository | None:
    dsn = os.getenv("EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN", "").strip()
    scope_key = os.getenv("EMPIRE_OUTBOUND_SCOPE_KEY", "").strip()
    if not dsn or not scope_key:
        return None
    return PostgresDeliverabilityRepository(
        dsn,
        scope_key,
        connect_factory=connect_factory,
    )


def configured_deliverability_writer_from_env(
    *,
    connect_factory: Callable | None = None,
) -> PostgresDeliverabilityEvidenceWriter | None:
    dsn = os.getenv("EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN", "").strip()
    scope_key = os.getenv("EMPIRE_OUTBOUND_SCOPE_KEY", "").strip()
    if not dsn or not scope_key:
        return None
    return PostgresDeliverabilityEvidenceWriter(
        dsn,
        scope_key,
        connect_factory=connect_factory,
    )
