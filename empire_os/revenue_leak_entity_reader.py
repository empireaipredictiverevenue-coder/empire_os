"""Restricted EmpireDB reader for entity-level Revenue Leak observations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from empire_os.revenue_leak_entity_observer import (
    observe_entity_revenue_leaks,
)


def read_entity_revenue_leaks(
    cursor: Any,
    *,
    as_of: datetime,
    window_days: int = 31,
) -> list:
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("as_of must include timezone")

    as_of = as_of.astimezone(timezone.utc)

    if not isinstance(window_days, int):
        raise ValueError("window_days must be integer")

    if window_days < 1 or window_days > 31:
        raise ValueError("window_days must be between 1 and 31")

    start = as_of - timedelta(days=window_days)

    # Read only intents that have an entity and at least one delivery
    # in the bounded observation window.
    cursor.execute(
        """
        SELECT DISTINCT
            i.id,
            i.entity_id
        FROM public.outbound_intents i
        JOIN public.outbound_events e
          ON e.intent_id = i.id
        WHERE i.entity_id IS NOT NULL
          AND e.event_type = 'delivered'
          AND e.occurred_at >= %s
          AND e.occurred_at < %s
        ORDER BY i.id
        """,
        (start, as_of),
    )

    intents = [
        {"id": str(row[0]), "entity_id": str(row[1])}
        for row in cursor.fetchall()
    ]

    if not intents:
        return []

    intent_ids = [row["id"] for row in intents]

    cursor.execute(
        """
        SELECT
            e.id,
            e.intent_id,
            e.event_type,
            e.occurred_at
        FROM public.outbound_events e
        WHERE e.intent_id = ANY(%s::uuid[])
          AND e.event_type = 'delivered'
          AND e.occurred_at >= %s
          AND e.occurred_at < %s
        ORDER BY e.occurred_at, e.id
        """,
        (intent_ids, start, as_of),
    )

    events = [
        {
            "id": str(row[0]),
            "intent_id": str(row[1]),
            "event_type": row[2],
            "occurred_at": row[3],
        }
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT
            r.id,
            r.intent_id,
            r.classification,
            r.received_at
        FROM public.outbound_replies r
        WHERE r.intent_id = ANY(%s::uuid[])
          AND r.received_at >= %s
          AND r.received_at < %s
        ORDER BY r.received_at, r.id
        """,
        (intent_ids, start, as_of),
    )

    replies = [
        {
            "id": str(row[0]),
            "intent_id": str(row[1]),
            "classification": row[2],
            "received_at": row[3],
        }
        for row in cursor.fetchall()
    ]

    return observe_entity_revenue_leaks(
        intents=intents,
        events=events,
        replies=replies,
        start=start,
        end=as_of,
    )
