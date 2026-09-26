"""Least-privilege read transport for Conversation OS."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence


class ConversationReadError(RuntimeError):
    pass


ROLE = "empire_conversation_reader"


class PostgresConversationReadRepository:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise ConversationReadError(
                "dedicated conversation reader DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise ConversationReadError(
                    "psycopg is required for conversation reads"
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
        params: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    return [
                        self._row_dict(cursor, row)
                        for row in rows
                    ]
        except Exception as exc:
            raise ConversationReadError(
                "conversation read failed"
            ) from exc

    def timeline(
        self,
        *,
        conversation_id: str,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        return self._read(
            """
            SELECT
              e.conversation_id,e.event_type,e.direction,e.actor,
              e.body_text,e.provider_event_id,e.evidence,
              e.occurred_at,e.created_at
            FROM public.empire_conversation_events e
            WHERE e.conversation_id = %s
            ORDER BY e.occurred_at ASC, e.id ASC
            LIMIT %s
            """,
            (conversation_id, bounded),
        )

    def conversation(
        self,
        *,
        conversation_id: str,
    ) -> Mapping[str, Any] | None:
        rows = self._read(
            """
            SELECT
              c.id,c.channel,c.state,c.prospect_id,c.entity_id,
              c.buyer_id,c.opportunity_id,c.closer_case_id,
              c.external_conversation_id,c.provider,
              c.opened_at,c.updated_at
            FROM public.empire_conversations c
            WHERE c.id = %s
            LIMIT 1
            """,
            (conversation_id,),
        )
        return rows[0] if rows else None
