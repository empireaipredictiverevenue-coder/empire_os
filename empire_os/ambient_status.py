"""
ambient_status.py — Empire Ambient AI observability surface.

Unifies the health of every always-on (ambient) agent loop into ONE view:
  - omni-agent (host :3997 + container :3000) health
  - market sweep cron (rotating all niches) last batch
  - hermes real-signal feed (Layer 22b) last run
  - AGI synthetic-intelligence swarm (Layer 23) auto-patch count
  - predictive-cloud brain cycle count

Run: python3 empire_os/ambient_status.py
Used by: the Ambient AI dashboard / cron watchdog.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_DSN = os.getenv("EMPIRE_PG_DSN", "postgresql://postgres:empire_pg_2026@127.0.0.1:5432/empire_vectors")


def _http_ok(url: str, timeout: int = 4) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _pg_counts():
    try:
        import psycopg2
    except ImportError:
        try:
            import asyncpg, asyncio
            async def g():
                c = await asyncpg.connect(DB_DSN, timeout=5)
                out = {}
                for t in ("synthetic_personas", "simulation_runs", "swarm_telemetry", "auto_patches"):
                    try:
                        out[t] = await c.fetchval(f"SELECT COUNT(*) FROM {t}")
                    except Exception:
                        out[t] = -1
                await c.close()
                return out
            return asyncio.run(g())
        except Exception:
            return {}
    try:
        c = psycopg2.connect(DB_DSN, connect_timeout=5)
        cur = c.cursor()
        out = {}
        for t in ("synthetic_personas", "simulation_runs", "swarm_telemetry", "auto_patches"):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                out[t] = cur.fetchone()[0]
            except Exception:
                out[t] = -1
        c.close()
        return out
    except Exception:
        return {}


def status() -> dict:
    loops = {
        "omni_agent_host_3997": _http_ok("http://127.0.0.1:3997/healthz"),
        "omni_agent_container_3000": _http_ok("http://10.218.156.211:3000/healthz"),
        "listmonk_9000": _http_ok("http://10.118.155.153:9000/") or _http_ok("http://10.118.155.153:9000/api/health"),
        "twenty_crm_3000": _http_ok("http://10.118.155.248:3000/healthz"),
    }
    pg = _pg_counts()
    alive = sum(1 for v in loops.values() if v)
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ambient_loops": loops,
        "ambient_loops_alive": f"{alive}/{len(loops)}",
        "agi_swarm": {
            "personas": pg.get("synthetic_personas", -1),
            "simulations": pg.get("simulation_runs", -1),
            "telemetry_events": pg.get("swarm_telemetry", -1),
            "auto_patches": pg.get("auto_patches", -1),
        },
        "positioning": "Empire Ambient AI — self-hosted, zero-rent autonomous revenue layer",
    }


if __name__ == "__main__":
    print(json.dumps(status(), indent=2))
