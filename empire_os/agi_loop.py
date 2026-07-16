"""
AGI Loop — continuous in-process orchestrator that runs all AGI agents
in parallel forever, with backoff and self-recovery.

Replaces cron-based scheduling with a single always-on background task.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("agi_loop")


class AgiLoop:
    """Run all AGI agents continuously with shared backoff + cycle metrics.

    Loops:
      - agi-scout     (every 5 min)
      - agi-marketing (every 10 min)
      - agi-sales     (every 2 min)
      - agi-closer    (every 3 min)
      - ceo brief     (every 60 min)
    """

    def __init__(
        self,
        agi_scout_client,
        agi_marketing_client,
        agi_sales_agent,
        agi_closer_agent,
        ceo_brief_fn,
        intervals: Optional[dict] = None,
    ):
        self.clients = {
            "agi-scout": (agi_scout_client, "tick", 300),       # 5 min
            "agi-marketing": (agi_marketing_client, "tick", 600),  # 10 min
            "agi-sales": (agi_sales_agent, "tick", 120),         # 2 min
            "agi-closer": (agi_closer_agent, "tick", 180),       # 3 min
            "ceo-brief": (ceo_brief_fn, "tick", 3600),           # 60 min
        }
        if intervals:
            for name, secs in intervals.items():
                if name in self.clients:
                    obj, method, _ = self.clients[name]
                    self.clients[name] = (obj, method, secs)

        self.metrics = {name: {"cycles": 0, "last_run": None, "last_error": None}
                       for name in self.clients}
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def _run_loop(self, name: str, fn, method: str, interval: int):
        """Run one agent on its interval with backoff on errors."""
        logger.info("Starting %s loop (interval=%ds)", name, interval)
        while not self._stop.is_set():
            try:
                # Run in a thread pool so we don't block the event loop
                result = await asyncio.to_thread(getattr(fn, method))
                self.metrics[name]["cycles"] += 1
                self.metrics[name]["last_run"] = datetime.now(timezone.utc).isoformat()
                self.metrics[name]["last_error"] = None
                logger.info("%s cycle #%d: %s", name, self.metrics[name]["cycles"], str(result)[:200])
            except Exception as e:
                self.metrics[name]["last_error"] = str(e)
                logger.exception("%s cycle failed", name)
                # Backoff: 60s on error, then resume normal cadence
                await asyncio.sleep(60)
                continue

            # Wait for next cycle (interruptible)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                break  # stop signal received
            except asyncio.TimeoutError:
                pass  # interval elapsed, run again

    async def start(self):
        """Spawn a task per agent."""
        self._stop.clear()
        for name, (fn, method, interval) in self.clients.items():
            task = asyncio.create_task(
                self._run_loop(name, fn, method, interval),
                name=f"loop-{name}",
            )
            self._tasks.append(task)
        logger.info("AGI Loop started with %d agents", len(self._tasks))

    async def stop(self):
        """Stop all loops gracefully."""
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("AGI Loop stopped")

    def status(self) -> dict:
        """Return current loop metrics for the dashboard."""
        return {
            "running": len(self._tasks) > 0,
            "agents": self.metrics,
            "intervals": {n: c[2] for n, c in self.clients.items()},
        }