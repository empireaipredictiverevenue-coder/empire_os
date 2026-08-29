"""
Empire OS DB Adapter — runtime schema-aware query layer.

The host's /root/empire_os/empire_os.db has the LEGACY schema (lead_ref, name,
no niche/metro/status). The container's DB has the NEW schema. Scripts that
need to read either schema can use this adapter.

Usage:
    from empire_os_db_adapter import get_lane_leads_by_niche
    leads = get_lane_leads_by_niche("roofing")

The adapter queries whichever DB has the relevant column. For writes it
delegates to the hub at http://10.118.155.218:8081 (or HUB_URL env var).
"""
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
from typing import Any, Optional

HOST_DB = os.environ.get("HOST_DB", "/root/empire_os/empire_os.db")
HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")


def _host_cols(table: str) -> set[str]:
    """Return column names from host DB for a table."""
    try:
        con = sqlite3.connect(HOST_DB, timeout=10.0)
        cur = con.execute(f"PRAGMA table_info({table})")
        cols = {r[1] for r in cur.fetchall()}
        con.close()
        return cols
    except Exception:
        return set()


def _container_query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SQL query against the container's DB via incus exec."""
    script = (
        "import sqlite3, json\n"
        f"c = sqlite3.connect('/root/empire_os/empire_os.db', timeout=30.0)\n"
        f"cur = c.execute({json.dumps(sql)}, {json.dumps(list(params))})\n"
        "cols = [d[0] for d in cur.description] if cur.description else []\n"
        "print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()]))\n"
    )
    r = subprocess.run(
        ["incus", "exec", "empire-hub", "--",
         "/root/venv/bin/python3", "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    if not r.stdout.strip():
        return []
    try:
        return json.loads(r.stdout.strip())
    except Exception:
        return []


def get_lane_leads_count_by_niche() -> list[tuple[str, int]]:
    """Return [(niche, count), ...] sorted by count desc. Reads from container
    (which has the niche column).
    """
    rows = _container_query(
        "SELECT niche, COUNT(*) AS n FROM lane_leads "
        "WHERE status='pending' AND niche IS NOT NULL AND niche != '' "
        "GROUP BY niche ORDER BY n DESC LIMIT 50"
    )
    return [(r["niche"], r["n"]) for r in rows]


def get_empty_lanes(limit: int = 60) -> list[dict]:
    """Get top empty lanes from container's lanes table."""
    rows = _container_query(
        "SELECT id, sub_niche, metro, seat_price, lane_number FROM lanes "
        "WHERE (occupied_by IS NULL OR occupied_by='') AND seat_price > 0 "
        "AND sub_niche IS NOT NULL AND sub_niche != '' "
        "AND metro IS NOT NULL AND metro != '' "
        "ORDER BY seat_price DESC, lane_number ASC LIMIT ?",
        (limit,),
    )
    return rows


def lookup_tenant_by_email(email: str) -> Optional[str]:
    """Look up tenant_id by email from container DB."""
    rows = _container_query(
        "SELECT tenant_id FROM si_tenant WHERE email=? LIMIT 1", (email,)
    )
    return rows[0]["tenant_id"] if rows else None


def get_si_tenant_count() -> int:
    rows = _container_query("SELECT COUNT(*) AS n FROM si_tenant")
    return rows[0]["n"] if rows else 0


def get_si_subscription_count() -> int:
    rows = _container_query("SELECT COUNT(*) AS n FROM si_subscription")
    return rows[0]["n"] if rows else 0


def get_si_charges_pending() -> tuple[int, float]:
    rows = _container_query(
        "SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents "
        "FROM si_charges WHERE status='pending'"
    )
    if not rows:
        return 0, 0.0
    return rows[0]["n"], rows[0]["cents"] / 100.0


def hub_post(path: str, body: dict, timeout: int = 15) -> dict:
    """POST JSON to the hub."""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            f"{HUB_URL}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"http_{e.code}", "body": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)[:300]}


def hub_get(path: str, params: Optional[dict] = None, timeout: int = 10) -> dict:
    """GET JSON from the hub."""
    import urllib.request
    import urllib.error
    from urllib.parse import urlencode
    url = f"{HUB_URL}{path}"
    if params:
        url += "?" + urlencode(params)
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"http_{e.code}", "body": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)[:300]}