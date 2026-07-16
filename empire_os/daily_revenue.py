"""
Daily Revenue — settlement → snapshot pipeline.

Rolls up settlements into daily revenue snapshots. The snapshot is
idempotent (UPSERT by composite key (snapshot_date, tenant_id)),
so re-running for the same day overwrites the previous rollup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from empire_os.funnel import SQLiteBackend

logger = logging.getLogger("daily_revenue")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS daily_revenue_snapshots (
    snapshot_date    TEXT NOT NULL,
    tenant_id        TEXT NOT NULL DEFAULT 'default',
    gross_cents      INTEGER NOT NULL DEFAULT 0,
    settled_cents    INTEGER NOT NULL DEFAULT 0,
    settlement_count INTEGER NOT NULL DEFAULT 0,
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    PRIMARY KEY (snapshot_date, tenant_id)
);

CREATE TABLE IF NOT EXISTS si_settlements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id    TEXT NOT NULL,
    tenant_id      TEXT NOT NULL DEFAULT 'default',
    amount_cents   INTEGER NOT NULL,
    settled_at     TEXT NOT NULL,
    settled_by     TEXT DEFAULT 'system',
    notes          TEXT DEFAULT ''
);
"""


@dataclass
class SettlementRollup:
    """Result of a single day's revenue rollup."""
    date: str
    tenant_id: str
    gross_cents: int
    settlement_count: int


class DailyRevenueSnapshotter:
    """Rolls up settlements into daily revenue snapshots."""

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend

    def ensure_schema(self) -> None:
        self.backend.executescript(SCHEMA_SQL)
        self.backend.commit()

    def recompute_snapshot(
        self,
        snapshot_date: str,
        tenant_id: str = "default",
    ) -> SettlementRollup:
        """Compute the daily revenue snapshot for a given date.

        Idempotent: re-running for the same day overwrites the previous
        rollup (UPSERT via INSERT OR REPLACE).
        """
        cursor = self.backend.execute(
            """SELECT COALESCE(SUM(amount_cents), 0) AS gross_cents,
                      COUNT(*) AS settlement_count
               FROM si_settlements
               WHERE tenant_id = ?
                 AND DATE(settled_at) = ?
                 AND settled_by != 'voided'""",
            (tenant_id, snapshot_date),
        )
        row = cursor.fetchone()
        gross = row["gross_cents"]
        count = row["settlement_count"]

        self.backend.execute(
            """INSERT OR REPLACE INTO daily_revenue_snapshots
               (snapshot_date, tenant_id, gross_cents, settled_cents,
                settlement_count, updated_at)
               VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%f', 'now'))""",
            (snapshot_date, tenant_id, gross, gross, count),
        )
        self.backend.commit()

        logger.info(
            "Revenue snapshot %s/%s: $%d.%02d (%d settlements)",
            snapshot_date, tenant_id,
            gross // 100, gross % 100, count,
        )

        return SettlementRollup(
            date=snapshot_date,
            tenant_id=tenant_id,
            gross_cents=gross,
            settlement_count=count,
        )

    def yesterday(self, tenant_id: str = "default") -> SettlementRollup:
        """Convenience: roll up yesterday's revenue."""
        yesterday_date = (date.today() - timedelta(days=1)).isoformat()
        return self.recompute_snapshot(yesterday_date, tenant_id)


class DailyRevenueBriefWorker:
    """Worker that runs the daily revenue snapshot for the past N days.

    Wire this into a scheduler (cron, background task) to automate
    daily revenue rollups.

    The default deliver callable is a logger. Wire Telegram delivery
    by passing a custom `deliver=` callable.
    """

    def __init__(
        self,
        backend: SQLiteBackend,
        lookback_days: int = 7,
        tenant_id: str = "default",
        deliver: Optional[Callable[[str], None]] = None,
        run_at_hour: int = 6,
    ):
        self.backend = backend
        self.lookback_days = lookback_days
        self.tenant_id = tenant_id
        self._deliver = deliver or self._default_deliver
        self.run_at_hour = run_at_hour
        self.snapshotter = DailyRevenueSnapshotter(backend)

    @staticmethod
    def _default_deliver(message: str) -> None:
        logger.info("[brief deliver] %s", message)

    def tick(self) -> str:
        """Run the snapshot and deliver the brief."""
        lines = []

        for i in range(self.lookback_days):
            d = (date.today() - timedelta(days=i)).isoformat()
            try:
                result = self.snapshotter.recompute_snapshot(d, self.tenant_id)
                lines.append(
                    f"  {d}: ${result.gross_cents // 100}.{result.gross_cents % 100:02d} "
                    f"({result.settlement_count} settlements)"
                )
            except Exception as e:
                logger.warning("Failed to snapshot %s: %s", d, e)

        message = (
            f"📊 Daily Revenue Brief ({self.tenant_id})\n"
            f"{'─' * 40}\n" + "\n".join(lines)
        )

        self._deliver(message)
        return message
