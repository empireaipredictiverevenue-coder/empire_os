"""
Empire OS — Multi-seat per lane.

Schema migration: lanes.occupied_by is a single TEXT. To support N buyers per
lane (the way real lead markets work), we introduce lane_seats (1 row per
buyer-seat). Migration is non-destructive — existing occupied_by values are
backfilled into lane_seats.

API:
    occupy_seat(lane_id, tenant_id, tier="standard", expires_at=None)
        -> {seat_id, lane_id, tenant_id, tier, expires_at, ok}
    release_seat(lane_id, tenant_id) -> {released: int}
    list_lane_seats(lane_id) -> [seat rows]
    list_tenant_seats(tenant_id) -> [seat rows]
    get_seat_count(lane_id) -> int
    get_seat_limit(lane_id) -> int  # -1 = unlimited

Limits per lane (auto-derived from seat_price tier):
    seat_price >=  5000 -> max 1 seat (whale tier, exclusive)
    seat_price >=  1000 -> max 3 seats
    seat_price >=   500 -> max 5 seats
    seat_price >=   100 -> max 10 seats
    seat_price >      0 -> max 25 seats
    seat_price ==     0 -> unlimited
"""
from __future__ import annotations
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

CONTAINER_DB = "/root/empire_os/empire_os.db"


def _run_sql(sql: str, params: tuple = ()) -> None:
    """Run SQL on the container's DB (the source of truth)."""
    # Use repr() for params so Python None stays None (json gives JS null)
    import sys as _sys
    script = (
        "import sqlite3\n"
        f"c = sqlite3.connect('{CONTAINER_DB}', timeout=30.0)\n"
        f"_params = {list(params)!r}\n"
        f"c.execute({sql!r}, _params)\n"
        "c.commit()\n"
        "c.close()\n"
    )
    subprocess.run(
        ["incus", "exec", "empire-hub", "--",
         "/root/venv/bin/python3", "-c", script],
        capture_output=True, text=True, timeout=30,
    )


def _run_query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SELECT on the container's DB and return list of dicts."""
    import json
    # Use repr() for params so Python None stays None (json gives JS null)
    script = (
        "import sqlite3, json\n"
        f"c = sqlite3.connect('{CONTAINER_DB}', timeout=30.0)\n"
        f"_params = {list(params)!r}\n"
        f"cur = c.execute({sql!r}, _params)\n"
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


def migrate() -> None:
    """Create lane_seats table + backfill from lanes.occupied_by (idempotent)."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS lane_seats (
        seat_id TEXT PRIMARY KEY,
        lane_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        tier TEXT DEFAULT 'standard',
        seat_price_usdc REAL DEFAULT 0,
        expires_at TEXT,
        occupied_at TEXT,
        active INTEGER DEFAULT 1,
        UNIQUE(lane_id, tenant_id)
    )
    """
    _run_sql(create_sql)
    # Backfill: any lane with occupied_by set but no lane_seats row
    rows = _run_query(
        "SELECT id, occupied_by, seat_price FROM lanes "
        "WHERE occupied_by IS NOT NULL AND occupied_by != '' "
        "AND id NOT IN (SELECT DISTINCT lane_id FROM lane_seats)"
    )
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        _run_sql(
            "INSERT OR IGNORE INTO lane_seats "
            "(seat_id, lane_id, tenant_id, tier, seat_price_usdc, occupied_at, active) "
            "VALUES (?, ?, ?, 'standard', ?, ?, 1)",
            (str(uuid.uuid4())[:12], r["id"], r["occupied_by"],
             r.get("seat_price") or 0, now),
        )


def _seat_limit(seat_price: float) -> int:
    """How many buyers can sit on a lane based on seat_price tier."""
    if seat_price <= 0:
        return 100  # effectively unlimited
    if seat_price >= 5000:
        return 1   # exclusive whale
    if seat_price >= 1000:
        return 3
    if seat_price >= 500:
        return 5
    if seat_price >= 100:
        return 10
    return 25  # cheap lanes: many seats


def get_seat_limit(lane_id: str) -> int:
    rows = _run_query("SELECT seat_price FROM lanes WHERE id=?", (lane_id,))
    if not rows:
        return 0
    return _seat_limit(rows[0].get("seat_price") or 0)


def get_seat_count(lane_id: str, active_only: bool = True) -> int:
    where = "WHERE lane_id=? AND active=1" if active_only else "WHERE lane_id=?"
    rows = _run_query(f"SELECT COUNT(*) AS n FROM lane_seats {where}", (lane_id,))
    return rows[0]["n"] if rows else 0


def occupy_seat(lane_id: str, tenant_id: str, tier: str = "standard",
               expires_at: str | None = None) -> dict:
    """Occupy a seat on a lane for a tenant. Multi-seat per lane allowed."""
    # Verify lane exists
    lane = _run_query("SELECT id, seat_price FROM lanes WHERE id=?", (lane_id,))
    if not lane:
        return {"ok": False, "error": "lane_not_found"}
    seat_price = lane[0].get("seat_price") or 0
    limit = _seat_limit(seat_price)
    cur_count = get_seat_count(lane_id, active_only=True)

    # Reuse existing seat if tenant already has one (idempotent)
    existing = _run_query(
        "SELECT seat_id FROM lane_seats WHERE lane_id=? AND tenant_id=?",
        (lane_id, tenant_id),
    )
    if existing:
        return {"ok": True, "seat_id": existing[0]["seat_id"],
                "lane_id": lane_id, "tenant_id": tenant_id,
                "reused": True, "seats_used": cur_count,
                "seats_limit": limit}

    if cur_count >= limit:
        return {"ok": False, "error": "lane_full",
                "seats_used": cur_count, "seats_limit": limit,
                "seat_price_usdc": seat_price}

    seat_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    _run_sql(
        "INSERT INTO lane_seats (seat_id, lane_id, tenant_id, tier, "
        "seat_price_usdc, expires_at, occupied_at, active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (seat_id, lane_id, tenant_id, tier, seat_price, expires_at, now),
    )
    # Also update lanes.occupied_by to comma-separated list for back-compat
    occupants = get_occupants(lane_id)
    _run_sql(
        "UPDATE lanes SET occupied_by=? WHERE id=?",
        (",".join(sorted(set(occupants + [tenant_id])))[:200], lane_id),
    )
    return {"ok": True, "seat_id": seat_id,
            "lane_id": lane_id, "tenant_id": tenant_id,
            "seats_used": cur_count + 1, "seats_limit": limit,
            "tier": tier, "expires_at": expires_at}


def release_seat(lane_id: str, tenant_id: str) -> dict:
    rows = _run_query(
        "SELECT seat_id FROM lane_seats WHERE lane_id=? AND tenant_id=? AND active=1",
        (lane_id, tenant_id),
    )
    if not rows:
        return {"released": 0, "reason": "no_active_seat"}
    _run_sql(
        "UPDATE lane_seats SET active=0 WHERE seat_id=?",
        (rows[0]["seat_id"],),
    )
    # Refresh lanes.occupied_by
    occupants = [o for o in get_occupants(lane_id) if o != tenant_id]
    _run_sql(
        "UPDATE lanes SET occupied_by=? WHERE id=?",
        (",".join(sorted(occupants))[:200] or None, lane_id),
    )
    return {"released": 1, "seat_id": rows[0]["seat_id"]}


def get_occupants(lane_id: str, active_only: bool = True) -> list[str]:
    where = "WHERE lane_id=? AND active=1" if active_only else "WHERE lane_id=?"
    rows = _run_query(
        f"SELECT tenant_id FROM lane_seats {where} ORDER BY occupied_at",
        (lane_id,),
    )
    return [r["tenant_id"] for r in rows]


def list_lane_seats(lane_id: str) -> list[dict]:
    return _run_query(
        "SELECT * FROM lane_seats WHERE lane_id=? AND active=1 "
        "ORDER BY occupied_at",
        (lane_id,),
    )


def list_tenant_seats(tenant_id: str) -> list[dict]:
    return _run_query(
        "SELECT * FROM lane_seats WHERE tenant_id=? AND active=1 "
        "ORDER BY occupied_at DESC",
        (tenant_id,),
    )


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    if cmd == "migrate":
        migrate()
        print("lane_seats table migrated; backfilled from occupied_by")
    elif cmd == "occupy":
        import json as _json
        lane_id = sys.argv[2]
        tenant_id = sys.argv[3]
        tier = sys.argv[4] if len(sys.argv) > 4 else "standard"
        print(_json.dumps(occupy_seat(lane_id, tenant_id, tier=tier), indent=2))
    elif cmd == "release":
        import json as _json
        lane_id = sys.argv[2]
        tenant_id = sys.argv[3]
        print(_json.dumps(release_seat(lane_id, tenant_id), indent=2))
    elif cmd == "list":
        import json as _json
        lane_id = sys.argv[2]
        seats = list_lane_seats(lane_id)
        print(_json.dumps({"lane_id": lane_id, "seats_used": len(seats),
                           "seats_limit": get_seat_limit(lane_id),
                           "seats": seats}, indent=2))
    else:
        print(f"unknown cmd: {cmd}")
        sys.exit(1)