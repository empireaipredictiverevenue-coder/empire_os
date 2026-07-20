#!/usr/bin/env python3
"""Empire OS — connect market-sweep leads (crm_leads) into the Empire Cortex
eval product (real Omega lead grading + USDC settlement).

Grades via OmegaScore DIRECTLY (pure-python, ~0ms, NO per-lead DB write to
si_funnel_events) so we avoid the lock contention that slowed the old path.
Final grades are batch-written to crm_leads with a lock-retry guard.
Buyers browsing /evaluate then see these graded leads for purchase.

Run: /root/venv/bin/python3 empire_os/eval_connect_sweeps.py
"""
import sqlite3, sys, json, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
EVAL_BUYER = "sweep_feed"  # owner tenant all swept leads grade under


def _c():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _grade_row(r) -> tuple[str, float]:
    """Grade one crm_leads row via OmegaScore directly (no funnel DB write)."""
    from empire_os.omega_os import OmegaScore
    from empire_os.agents.evaluation_product import grade_for
    from empire_os.lane_router import match_niche

    details = f"{r['business_name']} — {r['niche']} in {r['city']}, {r['state']}"
    matches = match_niche(details or "")
    tort = matches[0][0] if matches else "unknown"
    omega = OmegaScore(
        tort_key=tort,
        details=details,
        source="market_sweep",
        has_phone=bool(r["phone"]),
        has_zip=bool(r["zip"]),
        has_name=bool(r["business_name"]),
    ).compute()
    total = (omega["total"] or 0) / 100.0  # 0-1
    return grade_for(total), round(total, 3)


def _exec_batch(c, sql, rows):
    for _ in range(5):
        try:
            c.executemany(sql, rows)
            c.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                time.sleep(1)
                continue
            raise


def main(write: bool = True) -> dict:
    c = _c()
    for col in ("eval_grade", "eval_omega"):
        try:
            c.execute(f"ALTER TABLE crm_leads ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    rows = c.execute(
        "SELECT id, business_name, niche, city, state, phone, zip "
        "FROM crm_leads WHERE source='market_sweep' AND eval_grade IS NULL "
        "LIMIT 2000"
    ).fetchall()

    grades = {"A": 0, "B": 0, "C": 0, "D": 0}
    graded = 0
    batch = []
    for r in rows:
        try:
            g, o = _grade_row(r)
        except Exception:
            g, o = "D", 0.0
        grades[g] = grades.get(g, 0) + 1
        batch.append((g, o, r["id"]))
        graded += 1
        if write and len(batch) >= 100:
            _exec_batch(c,
                "UPDATE crm_leads SET eval_grade=?, eval_omega=? WHERE id=?",
                batch)
            batch = []
    if write and batch:
        _exec_batch(c,
            "UPDATE crm_leads SET eval_grade=?, eval_omega=? WHERE id=?", batch)
    c.close()
    return {"graded": graded, "grades": grades,
            "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    res = main(write=True)
    print(json.dumps(res, indent=2))
    print(f"\nGraded {res['graded']} sweep leads | "
          f"A={res['grades']['A']} B={res['grades']['B']} "
          f"C={res['grades']['C']} D={res['grades']['D']}")
