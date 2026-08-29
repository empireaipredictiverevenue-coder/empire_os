#!/usr/bin/env python3
"""
Empire OS SI Brain — MCP Bridge (si_mcp_bridge.py)
===================================================
SIMCPBridge connects SI Brain components to the MCP Database Bridge.
Exposes strategy ops, parameter management, adaptation logging as MCP tools.

Circuit breaker: if DB unreachable, trips open, blocks writes, logs.
Agents NEVER touch DB directly — only via these tools.

Extends empire_mcp (A2A + AEO) with SI Brain surface.
"""

import sqlite3
import json
import time
from datetime import datetime, timezone

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

import sys
sys.path.insert(0, "/root/empire_os")
from empire_os import si_strategy, si_adaptive

DB = "/root/empire_os/empire_os.db"

# circuit breaker state
_cb = {"open": False, "fail_ts": 0, "cooldown": 30, "failures": 0}


def _db():
    if _cb["open"]:
        raise RuntimeError("circuit_breaker_open")
    try:
        c = sqlite3.connect(DB, timeout=30)
        c.row_factory = sqlite3.Row
        _cb["failures"] = 0
        return c
    except Exception:
        _cb["failures"] += 1
        if _cb["failures"] >= 3:
            _cb["open"] = True
            _cb["fail_ts"] = time.time()
        raise


def _breaker_tick():
    if _cb["open"] and (time.time() - _cb["fail_ts"]) > _cb["cooldown"]:
        _cb["open"] = False
        _cb["failures"] = 0


if FastMCP:
    mcp = FastMCP("empire_si_mcp")

    @mcp.tool(name="si_list_strategies", description="List active SI Brain campaign strategies + scores.")
    def si_list_strategies() -> str:
        _breaker_tick()
        c = _db()
        rows = c.execute("SELECT name, archetype, win_rate, revenue_generated, confidence, active FROM si_strategies").fetchall()
        c.close()
        return json.dumps([dict(r) for r in rows], indent=2)

    @mcp.tool(name="si_record_outcome", description="Record campaign outcome (calls, revenue, win) for a strategy.")
    def si_record_outcome(strategy_name: str, calls_generated: int = 0, revenue_captured: float = 0.0, win: int = 0) -> str:
        _breaker_tick()
        c = _db()
        row = c.execute("SELECT id FROM si_strategies WHERE name=?", (strategy_name,)).fetchone()
        c.close()
        if not row:
            return json.dumps({"error": "unknown_strategy", "name": strategy_name})
        res = si_strategy.record_outcome(row["id"], calls_generated, revenue_captured, win)
        return json.dumps(res)

    @mcp.tool(name="si_evolve", description="Run one strategy evolution pass (mutate winners, deactivate losers).")
    def si_evolve() -> str:
        _breaker_tick()
        events = si_strategy.evolve(verbose=False)
        return json.dumps({"events": events, "count": len(events)})

    @mcp.tool(name="si_parameters", description="Current adopted SI parameters across subsystems.")
    def si_parameters() -> str:
        _breaker_tick()
        c = _db()
        rows = c.execute("SELECT subsystem, param_key, param_value, adopted_at FROM si_parameters").fetchall()
        c.close()
        return json.dumps([dict(r) for r in rows], indent=2)

    @mcp.tool(name="si_set_parameter", description="Set an SI parameter for a subsystem (logs adaptation).")
    def si_set_parameter(subsystem: str, param_key: str, value: float, reason: str = "mcp") -> str:
        _breaker_tick()
        si_adaptive.set_parameter(subsystem, param_key, value, reason)
        return json.dumps({"ok": True, "key": f"{subsystem}.{param_key}", "value": value})

    @mcp.tool(name="si_health", description="SI Brain + bridge health (components, circuit breaker).")
    def si_health() -> str:
        _breaker_tick()
        from empire_os import si_brain
        return json.dumps({"bridge": _cb, "components": si_brain.health()}, indent=2)

    def run():
        mcp.run(transport="http", host="0.0.0.0", port=8083)
else:
    def run():
        raise RuntimeError("fastmcp not installed")


if __name__ == "__main__":
    run()
