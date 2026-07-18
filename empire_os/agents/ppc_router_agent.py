"""
PPC Router Agent — wraps /root/empire_os/ppc_router.py as a SyntheticAgent
so it lands on pm2 + gets supervised + has a SOUL.

Why a wrapper:
  /root/empire_os/ppc_router.py is a long-lived BaseHTTPRequestHandler
  on port 9200 (the billing server). It already does its job. This
  agent:
    1. launches ppc_router.py as a subprocess on startup
    2. ticks every 60s to audit pending invoices from si_ppc_invoices
       where created_at < (now - 24h) — "collect what's owed"
    3. tails /root/feedback/ppc_events.jsonl for ERROR / failed
       charge lines — alerts via hermes-gateway
    4. liveness pings /health on port 9200 each tick — restart
       ppc_router.py if it's down

NO cron, NO scripts. Agentic loop.

Cadence:
  60s — healthcheck + audit
"""
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.synthetic_agents import SyntheticAgent

ROLE_DIR = Path("/root/ppc_router")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
TICK_INTERVAL = 60  # 1 min

HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
DB_PATH = os.environ.get("DB_PATH", "/root/empire_os/empire_os.db")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100"
)

ROUTER_SCRIPT = "/root/empire_os/empire_os/ppc_router.py"
VENV_PY = "/root/venv/bin/python3"
ROUTER_PORT = 9200
ROUTER_HEALTH = f"http://127.0.0.1:{ROUTER_PORT}/health"
ROUTER_LOG = Path("/root/feedback/ppc_router.log")


def _router_alive() -> bool:
    try:
        with urllib.request.urlopen(ROUTER_HEALTH, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _start_router() -> subprocess.Popen | None:
    """Launch ppc_router.py as subprocess. Returns None if launch failed."""
    try:
        ROUTER_LOG.parent.mkdir(parents=True, exist_ok=True)
        log = open(ROUTER_LOG, "ab")
        return subprocess.Popen(
            [VENV_PY, ROUTER_SCRIPT],
            stdout=log, stderr=log,
            cwd="/root/empire_os",
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except Exception:
        return None


def _pending_aged_invoices(hours: int = 24) -> list[dict]:
    """Find si_ppc_invoices WHERE status='open' AND created_at older than Nh."""
    try:
        cnx = sqlite3.connect(DB_PATH)
        cnx.row_factory = sqlite3.Row
        rows = [dict(r) for r in cnx.execute(
            "SELECT invoice_id, amount_cents, head, created_at, buyer_id "
            "FROM si_ppc_invoices "
            "WHERE status='open' "
            "AND datetime(created_at) < datetime('now', ?)",
            (f"-{hours} hours",)
        ).fetchall()]
        cnx.close()
        return rows
    except Exception:
        return []


def _recent_failed_charges(window_min: int = 30) -> list[str]:
    """Tail ppc_events.jsonl for ERROR/FAIL lines within window."""
    events = Path("/root/feedback/ppc_events.jsonl")
    if not events.exists():
        return []
    cutoff = time.time() - window_min * 60
    out = []
    try:
        with events.open() as f:
            for ln in f:
                try:
                    e = json.loads(ln)
                    ts = e.get("ts") or e.get("created_at") or ""
                    # accept ISO or epoch; we only need recent ones
                    e_time = e.get("ts_epoch") or (
                        time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
                        if ts[:19].count(":") == 2 else 0
                    )
                    if e_time >= cutoff and (
                        "fail" in str(e).lower() or
                        "error" in str(e).lower()
                    ):
                        out.append(json.dumps(e)[:200])
                except Exception:
                    continue
    except Exception:
        pass
    return out[-5:]


def _alert(msg: str) -> None:
    """Best-effort alert via hermes-gateway; fall back to print on fail."""
    try:
        req = urllib.request.Request(
            f"{HERMES_GATEWAY_URL}/v1/notify/alert",
            data=json.dumps({"msg": msg, "source": "ppc-router-agent"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=4)
    except Exception:
        print(json.dumps({"alert": msg, "delivered": False}))


class PpcRouterAgent(SyntheticAgent):
    """Wraps ppc_router.py + audits its bills every minute."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._router_proc: subprocess.Popen | None = None

    def observe(self) -> dict:
        state = {
            "router_alive": False,
            "aged_open_invoices": [],
            "recent_failures": [],
            "ts": time.time(),
        }
        state["router_alive"] = _router_alive()
        if not state["router_alive"]:
            self._router_proc = _start_router()
        state["aged_open_invoices"] = _pending_aged_invoices(24)
        state["recent_failures"] = _recent_failed_charges(30)
        return state

    def reason(self, state: dict) -> str:
        n_aged = len(state["aged_open_invoices"])
        n_fail = len(state["recent_failures"])
        return json.dumps({
            "router_alive": state["router_alive"],
            "aged_open": n_aged,
            "recent_failures": n_fail,
            "aged_total_usd": sum(
                inv.get("amount_cents", 0) / 100
                for inv in state["aged_open_invoices"]
            ),
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            d = {"raw": decision}
        aged = d.get("aged_open", 0)
        if aged >= 1:
            _alert(
                f"ppc-router: {aged} open invoice(s) "
                f"older than 24h totalling ${d.get('aged_total_usd', 0):.2f}"
            )
        if not d.get("router_alive"):
            return {"summary": "router-was-down-restarted",
                    "aged_open": aged,
                    "recent_failures": d.get("recent_failures", 0)}
        return {"summary": "ppc-router-tick-clean",
                "aged_open": aged,
                "recent_failures": d.get("recent_failures", 0)}


if __name__ == "__main__":
    agent = PpcRouterAgent(
        name="ppc-router-agent",
        role="ppc_router",
        health_url=f"http://127.0.0.1:{ROUTER_PORT}/health",
    )
    print(f"PPC router agent starting — tick interval {TICK_INTERVAL}s",
          flush=True)
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({
                "cycle": result.get("cycle"),
                "summary": result.get("result", {}).get("summary", ""),
            }), flush=True)
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff}), flush=True)
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
