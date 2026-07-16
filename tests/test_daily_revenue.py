"""
Tests for Daily Revenue persona.
"""

import pytest
from empire_os.funnel import SQLiteBackend
from empire_os.daily_revenue import (
    DailyRevenueSnapshotter,
    DailyRevenueBriefWorker,
)


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    return b


@pytest.fixture
def snap(backend):
    s = DailyRevenueSnapshotter(backend)
    s.ensure_schema()
    return s


class TestDailyRevenueSnapshotter:
    def test_empty_snapshot(self, snap):
        result = snap.recompute_snapshot("2026-07-12")
        assert result.gross_cents == 0
        assert result.settlement_count == 0

    def test_with_settlements(self, snap):
        # Add some settlements
        snap.backend.execute(
            """INSERT INTO si_settlements
               (prospect_id, amount_cents, settled_at, notes)
               VALUES (?, ?, ?, ?)""",
            ("p1", 50000, "2026-07-12T10:00:00", "roofing job"),
        )
        snap.backend.execute(
            """INSERT INTO si_settlements
               (prospect_id, amount_cents, settled_at, notes)
               VALUES (?, ?, ?, ?)""",
            ("p2", 75000, "2026-07-12T14:00:00", "hvac install"),
        )
        snap.backend.commit()

        result = snap.recompute_snapshot("2026-07-12")
        assert result.gross_cents == 125000  # $1250.00
        assert result.settlement_count == 2

    def test_idempotent_upsert(self, snap):
        """Re-running for the same day overwrites, doesn't double-count."""
        snap.backend.execute(
            """INSERT INTO si_settlements
               (prospect_id, amount_cents, settled_at, notes)
               VALUES (?, ?, ?, ?)""",
            ("p1", 100000, "2026-07-12T12:00:00", "big job"),
        )
        snap.backend.commit()

        r1 = snap.recompute_snapshot("2026-07-12")
        assert r1.gross_cents == 100000

        # Run again — should be same result
        r2 = snap.recompute_snapshot("2026-07-12")
        assert r2.gross_cents == 100000
        assert r2.settlement_count == 1

    def test_multi_day_rollup(self, snap):
        snap.backend.execute(
            "INSERT INTO si_settlements (prospect_id, amount_cents, settled_at) "
            "VALUES (?, ?, ?)", ("p1", 30000, "2026-07-11T10:00:00"),
        )
        snap.backend.execute(
            "INSERT INTO si_settlements (prospect_id, amount_cents, settled_at) "
            "VALUES (?, ?, ?)", ("p2", 60000, "2026-07-12T10:00:00"),
        )
        snap.backend.commit()

        r1 = snap.recompute_snapshot("2026-07-11")
        assert r1.gross_cents == 30000

        r2 = snap.recompute_snapshot("2026-07-12")
        assert r2.gross_cents == 60000

    def test_tenant_isolation(self, snap):
        snap.backend.execute(
            "INSERT INTO si_settlements (prospect_id, tenant_id, amount_cents, settled_at) "
            "VALUES (?, ?, ?, ?)", ("p1", "tenant_a", 50000, "2026-07-12T10:00:00"),
        )
        snap.backend.execute(
            "INSERT INTO si_settlements (prospect_id, tenant_id, amount_cents, settled_at) "
            "VALUES (?, ?, ?, ?)", ("p2", "tenant_b", 100000, "2026-07-12T10:00:00"),
        )
        snap.backend.commit()

        r_a = snap.recompute_snapshot("2026-07-12", "tenant_a")
        assert r_a.gross_cents == 50000

        r_b = snap.recompute_snapshot("2026-07-12", "tenant_b")
        assert r_b.gross_cents == 100000


class TestDailyRevenueBriefWorker:
    def test_tick_delivers(self, snap):
        delivered = []

        def fake_deliver(msg):
            delivered.append(msg)

        worker = DailyRevenueBriefWorker(
            snap.backend,
            lookback_days=3,
            deliver=fake_deliver,
        )
        worker.snapshotter.ensure_schema()

        msg = worker.tick()
        assert len(delivered) == 1
        assert "Daily Revenue Brief" in delivered[0]
        assert "$0.00" in msg
