"""
Legacy Auto-Pilot compatibility loop — OBSERVE ONLY.

The original implementation mutated the funnel, impersonated operator approval,
and attempted settlement. Those paths are retired. Canonical Phase 3E/3F
governed services own approval, sending, settlement evidence and revenue.

This module remains only so older hub imports/status surfaces do not break.
It never performs a mutating HTTP request.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("auto_pilot")


@dataclass
class CycleReport:
    cycle: int = 0
    started_at: str = ""
    matched: int = 0
    drafted: int = 0
    sent: int = 0
    replied: int = 0
    claimed: int = 0
    settled: int = 0
    revenue_cents: int = 0
    error: str = ""


class AutoPilot:
    """Read-only compatibility monitor for the retired legacy funnel."""

    def __init__(
        self,
        hub_url: str = "http://localhost:8080",
        match_limit: int = 10,
        draft_limit: int = 5,
        settle_rate: float = 0.5,
        send_rate: float = 0.8,
        reply_rate: float = 0.3,
        min_amount_cents: int = 100000,
        max_amount_cents: int = 500000,
    ):
        self.hub_url = hub_url.rstrip("/")
        self.match_limit = match_limit
        self.draft_limit = draft_limit
        self.settle_rate = settle_rate
        self.send_rate = send_rate
        self.reply_rate = reply_rate
        self.min_amount = min_amount_cents
        self.max_amount = max_amount_cents
        self.cycle = 0
        self.history: list = []
        self.totals = {
            "matched": 0, "drafted": 0, "sent": 0, "replied": 0,
            "claimed": 0, "settled": 0, "revenue_cents": 0,
        }

    def _http(self, method: str, path: str, payload: Optional[dict] = None) -> tuple:
        url = f"{self.hub_url}{path}"
        data = json.dumps(payload).encode() if payload else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status, json.loads(resp.read().decode())
        except Exception as e:
            logger.warning("%s %s failed: %s", method, path, e)
            return 0, {"error": str(e)}

    def run_cycle(self) -> CycleReport:
        """Run one full pipeline cycle."""
        self.cycle += 1
        # Short-circuit: if the last cycle found nothing across all stages,
        # skip the hub calls entirely (pipeline is empty — no point
        # hammering funnel/states and starving other requests).
        if getattr(self, "_last_empty", False):
            # one cheap health ping to confirm hub alive; skip if down
            st, _ = self._http("GET", "/health", {})
            if st != 200:
                report = CycleReport(cycle=self.cycle, started_at=datetime.now(timezone.utc).isoformat())
                report.error = "hub_unreachable"
                logger.warning("cycle %d: hub unreachable, skipping", self.cycle)
                return report
            logger.info("cycle %d: pipeline empty, skipping stage calls", self.cycle)
            return CycleReport(cycle=self.cycle, started_at=datetime.now(timezone.utc).isoformat())
        report = CycleReport(cycle=self.cycle, started_at=datetime.now(timezone.utc).isoformat())
        try:
            self._stage_observe(report)
        except Exception as e:
            report.error = str(e)
            logger.exception("cycle %d failed: %s", self.cycle, e)
        # mark emptiness for next cycle
        self._last_empty = all(
            getattr(report, k) == 0 for k in
            ["matched", "drafted", "sent", "replied", "claimed", "settled"]
        )

        # Accumulate totals
        for k in ["matched", "drafted", "sent", "replied", "claimed", "settled"]:
            self.totals[k] += getattr(report, k)
        self.totals["revenue_cents"] += report.revenue_cents
        self.history.append(asdict(report))
        logger.info(
            "cycle %d: matched=%d drafted=%d sent=%d replied=%d claimed=%d settled=%d $%.2f",
            report.cycle, report.matched, report.drafted, report.sent,
            report.replied, report.claimed, report.settled,
            report.revenue_cents / 100,
        )
        return report

    # ── Read-only compatibility observation ─────────────────────

    def _stage_observe(self, report: CycleReport):
        """Read legacy funnel counts without advancing any state."""
        _, data = self._http("GET", "/v1/funnel/states?state=discovered&limit=1")
        if data.get("error"):
            report.error = data["error"]
        return

    def _stage_match(self, report: CycleReport):
        """Legacy match mutation retired."""
        logger.info("_stage_match: blocked by governed architecture")
        return

    def _stage_draft(self, report: CycleReport):
        """Legacy draft mutation retired."""
        logger.info("_stage_draft: blocked by governed architecture")
        return

    def _stage_send(self, report: CycleReport):
        """Legacy send/approval mutation retired."""
        logger.info("_stage_send: blocked by governed architecture")
        return

    def _stage_reply(self, report: CycleReport):
        """Replies are captured by the real inbound/provider lifecycle only."""
        return

    def _stage_claim(self, report: CycleReport):
        """Legacy closer claim mutation retired."""
        logger.info("_stage_claim: blocked by governed architecture")
        return

    def _stage_settle(self, report: CycleReport):
        """Legacy settlement mutation retired."""
        logger.info("_stage_settle: blocked by governed architecture")
        return


    def run_forever(self, interval_seconds: int = 120):
        """Continuous loop — runs every N seconds forever."""
        logger.info("Auto-pilot starting, interval=%ds", interval_seconds)
        while True:
            self.run_cycle()
            time.sleep(interval_seconds)


def main():
    logging.basicConfig(level=logging.INFO, format="[auto-pilot] %(message)s")
    hub_url = "http://localhost:8080"
    # If we're inside the hub container, hub is on localhost
    pilot = AutoPilot(hub_url=hub_url, match_limit=10, draft_limit=5)
    pilot.run_forever(interval_seconds=60)


if __name__ == "__main__":
    main()