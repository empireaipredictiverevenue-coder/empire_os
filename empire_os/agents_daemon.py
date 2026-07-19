#!/usr/bin/env python3
"""Standalone AGI agent daemon.

Runs AgiLoop + AutoPilot in THIS process's own asyncio event loop, so they
never share (or saturate) the hub's uvicorn event loop. The hub starts PURE
API (EMPIRE_INPROC_AGENTS unset) and these agents run here as a separate pm2
daemon (empire-agents).

Each agent gets its own loop/process — one blocking LLM call can't freeze the
hub or the other agents.
"""
import os, sys, asyncio, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
log = logging.getLogger("empire-agents")

DB_PATH = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
HUB_URL = os.environ.get("EMPIRE_HUB_URL", "http://127.0.0.1:8081")
PORT = int(os.environ.get("EMPIRE_PORT", "8000"))


def build_backend():
    from empire_os.funnel import SQLiteBackend
    return SQLiteBackend(DB_PATH)


def build_agents(backend):
    from empire_os.agi_client import AgiScoutClient, AgiMarketingClient
    from empire_os.agent_core import OpenRouterClient
    from empire_os.agi_sales import AgiSalesAgent
    from empire_os.agi_closer import AgiCloserAgent

    agents = {}
    agents["agi_scout"] = AgiScoutClient()
    agents["agi_marketing"] = AgiMarketingClient()
    try:
        agents["agi_sales"] = AgiSalesAgent(
            backend=backend, llm=OpenRouterClient(model="tencent/hy3:free", timeout=8))
        log.info("agi-sales ready (OpenRouter hy3)")
    except Exception as e:
        log.warning("agi-sales skipped: %s", str(e)[:120]); agents["agi_sales"] = None
    try:
        agents["agi_closer"] = AgiCloserAgent(
            backend=backend, llm=OpenRouterClient(model="tencent/hy3:free", timeout=8))
        log.info("agi-closer ready (OpenRouter hy3)")
    except Exception as e:
        log.warning("agi-closer skipped: %s", str(e)[:120]); agents["agi_closer"] = None
    return agents


async def run_agi_loop(backend, agents):
    from empire_os.agi_loop import AgiLoop
    from empire_os.ceo import tick as ceo_tick_fn
    class _CeoProxy:
        def __init__(self, fn, b): self._fn, self._b = fn, b
        def tick(self): return self._fn(self._b)
    agi_loop = AgiLoop(
        agi_scout_client=agents["agi_scout"],
        agi_marketing_client=agents["agi_marketing"],
        agi_sales_agent=agents["agi_sales"],
        agi_closer_agent=agents["agi_closer"],
        ceo_brief_fn=_CeoProxy(ceo_tick_fn, backend),
    )
    await agi_loop.start()


async def run_auto_pilot():
    from empire_os.auto_pilot import AutoPilot
    ap = AutoPilot(hub_url=HUB_URL, match_limit=15, draft_limit=10,
                  reply_rate=0.4, settle_rate=0.6)
    interval = 60
    log.info("auto-pilot started — cycles every %ds against %s", interval, HUB_URL)
    while True:
        try:
            report = await asyncio.to_thread(ap.run_cycle)
            log.info("auto-pilot cycle %d: matched=%d drafted=%d sent=%d replied=%d claimed=%d settled=%d $%.2f",
                     report.cycle, report.matched, report.drafted, report.sent,
                     report.replied, report.claimed, report.settled, report.revenue_cents / 100)
        except Exception as e:
            log.warning("auto-pilot cycle failed: %s", str(e)[:160])
        await asyncio.sleep(interval)


async def main():
    backend = build_backend()
    # lane schema so agents have lanes to work
    try:
        from empire_os.lanes import ensure_lane_schema, seed_lanes
        ensure_lane_schema(backend); seed_lanes(backend)
    except Exception as e:
        log.warning("lane init skipped: %s", str(e)[:120])
    agents = build_agents(backend)
    log.info("AGI agent daemon online (own event loop) — hub at %s", HUB_URL)
    await asyncio.gather(run_agi_loop(backend, agents), run_auto_pilot())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("agent daemon stopped")
