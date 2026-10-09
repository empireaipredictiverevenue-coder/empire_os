from datetime import datetime, timezone
from uuid import uuid4

import pytest

from empire_os.revenue_leak_entity_reader import (
    read_entity_revenue_leaks,
)


NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)


class Cursor:
    def __init__(self, batches):
        self.batches = list(batches)
        self.executions = []
        self.current = []

    def execute(self, sql, params):
        self.executions.append((sql, params))
        self.current = self.batches.pop(0)

    def fetchall(self):
        return list(self.current)


def test_reader_uses_canonical_event_intent_entity_lineage():
    intent_id = uuid4()
    entity_id = uuid4()
    event_id = uuid4()

    cur = Cursor(
        [
            [(intent_id, entity_id)],
            [
                (
                    event_id,
                    intent_id,
                    "delivered",
                    datetime(
                        2026, 10, 5, 12, 0,
                        tzinfo=timezone.utc,
                    ),
                )
            ],
            [],
        ]
    )

    rows = read_entity_revenue_leaks(
        cur,
        as_of=NOW,
        window_days=31,
    )

    assert len(rows) == 1
    assert rows[0].entity_id == str(entity_id)
    assert rows[0].delivered_count == 1
    assert rows[0].commercial_reply_count == 0

    joined_sql = cur.executions[0][0]

    assert "public.outbound_intents" in joined_sql
    assert "public.outbound_events" in joined_sql
    assert "e.intent_id = i.id" in joined_sql
    assert "i.entity_id IS NOT NULL" in joined_sql


def test_reader_returns_empty_without_entity_bound_delivery():
    cur = Cursor([[]])

    rows = read_entity_revenue_leaks(
        cur,
        as_of=NOW,
    )

    assert rows == []
    assert len(cur.executions) == 1


@pytest.mark.parametrize("days", [0, 32, -1])
def test_window_fails_closed(days):
    cur = Cursor([])

    with pytest.raises(ValueError, match="between 1 and 31"):
        read_entity_revenue_leaks(
            cur,
            as_of=NOW,
            window_days=days,
        )


def test_as_of_requires_timezone():
    cur = Cursor([])

    with pytest.raises(ValueError, match="timezone"):
        read_entity_revenue_leaks(
            cur,
            as_of=datetime(2026, 10, 6),
        )


def test_commercial_reply_prevents_leak_candidate():
    intent_id = uuid4()
    entity_id = uuid4()
    event_id = uuid4()
    reply_id = uuid4()

    cur = Cursor(
        [
            [(intent_id, entity_id)],
            [
                (
                    event_id,
                    intent_id,
                    "delivered",
                    datetime(
                        2026, 10, 5, 12, 0,
                        tzinfo=timezone.utc,
                    ),
                )
            ],
            [
                (
                    reply_id,
                    intent_id,
                    "positive",
                    datetime(
                        2026, 10, 5, 13, 0,
                        tzinfo=timezone.utc,
                    ),
                )
            ],
        ]
    )

    rows = read_entity_revenue_leaks(
        cur,
        as_of=NOW,
    )

    assert rows == []


def test_reader_has_no_write_sql():
    import inspect
    import empire_os.revenue_leak_entity_reader as module

    source = inspect.getsource(module)

    for forbidden in (
        "INSERT INTO",
        "UPDATE public.",
        "DELETE FROM",
        "TRUNCATE ",
        "DROP TABLE",
    ):
        assert forbidden not in source
