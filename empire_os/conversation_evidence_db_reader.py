"""Bounded, read-only original reply evidence source adapter.

No SELECT *, no subprocess argv credentials, no raw reply bodies or contacts.
This reads source-event metadata only. It cannot establish authenticity,
tenant authority, buyer intent, or commercial execution permission.
"""
from __future__ import annotations

from typing import Any, Callable
import os

MAX_ROWS = 750
READ_COLUMNS = {
    "public.outbound_replies": (
        "id", "intent_id", "provider_message_id", "classification", "received_at"
    ),
    "public.empire_conversation_events": (
        "id", "conversation_id", "event_type", "direction",
        "provider_event_id", "occurred_at"
    ),
}
SORT_COLUMNS = {
    "public.outbound_replies": "received_at",
    "public.empire_conversation_events": "occurred_at",
}


class EvidenceReadUnavailable(RuntimeError):
    """Sanitized failure: never contain the original DSN or database exception."""


def select_query(table: str, *, max_rows: int = MAX_ROWS) -> str:
    if table not in READ_COLUMNS:
        raise ValueError("unapproved reply source table")
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError("reply evidence row limit exceeded")
    cols = ", ".join(f'"{c}"' for c in READ_COLUMNS[table])
    # Both identifiers are selected from fixed, compile-time allowlists.
    schema, name = table.split(".")
    return (
        f'SELECT {cols} FROM "{schema}"."{name}" '
        f'ORDER BY "{SORT_COLUMNS[table]}" DESC NULLS LAST, "id" DESC '
        f'LIMIT {max_rows}'
    )


def read_reply_evidence(
    table: str,
    *,
    dsn: str | None = None,
    connect_factory: Callable[..., Any] | None = None,
    max_rows: int = MAX_ROWS,
) -> list[dict[str, Any]]:
    sql = select_query(table, max_rows=max_rows)
    if dsn is None:
        dsn = os.environ.get("EMPIREDB_DSN")
    if not dsn:
        raise EvidenceReadUnavailable("DEDICATED_REPLY_READER_CREDENTIAL_MISSING")
    if connect_factory is None:
        try:
            import psycopg
        except ImportError:
            raise EvidenceReadUnavailable("REPLY_READER_DRIVER_MISSING") from None
        connect_factory = psycopg.connect
    try:
        # A failed query rolls back; no partial source state is published.
        with connect_factory(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                cursor.execute(sql)
                rows = cursor.fetchall()
    except Exception:
        raise EvidenceReadUnavailable("REPLY_SOURCE_QUERY_FAILED") from None
    columns = READ_COLUMNS[table]
    result: list[dict[str, Any]] = []
    if len(rows) > max_rows:
        raise EvidenceReadUnavailable("REPLY_SOURCE_ROW_BOUND_EXCEEDED")
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != len(columns):
            raise EvidenceReadUnavailable("REPLY_SOURCE_SCHEMA_DRIFT")
        # Converting UUID/timestamp to strings happens in memory only. The
        # existing adjudicator stores hashes and reason codes, not these rows.
        record: dict[str, Any] = {}
        for name, value in zip(columns, row):
            if value is not None:
                record[name] = str(value) if not isinstance(value, (str, int, float, bool)) else value
        result.append(record)
    return result
