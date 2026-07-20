#!/usr/bin/env python3
"""Empire OS — connect market-sweep leads (crm_leads) into the Empire Cortex
eval product (real Omega lead grading + USDC settlement).

Pulls unscored crm_leads, grades them in-process via evaluation_product
(no HTTP overhead), writes the A/B/C/D grade + omega score back to crm_leads.
Buyers browsing /evaluate then see these graded leads for purchase.

Run: /root/venv/bin/python3 empire_os/eval_connect_sweeps.py
"""
import sqlite3, sys, json
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
EVAL_BUYER = "sweep_feed"  # owner tenant all swept leads grade under


def _c():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def main(write: bool = True) -> dict:
    from empire_os.agents import evaluation_product as EP

    c = _c()
    # add grade column if missing
    try:
        c.execute("ALTER TABLE crm_leads ADD COLUMN eval_grade TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE crm_leads ADD COLUMN eval_omega REAL")
    except sqlite3.OperationalError:
        pass

    # unscored leads (prefer warm/hot tiers we already scored)
    rows = c.execute(
        "SELECT id, business_name, niche, city, state, phone, website "
        "FROM crm_leads WHERE eval_grade IS NULL LIMIT 500"
    ).fetchall()

    grades = {"A": 0, "B": 0, "C": 0, "D": 0}
    graded = 0
    batch = []
    for r in rows:
        lead = {
            "name": r["business_name"],
            "details": f"{r['business_name']} — {r['niche']} in {r['city']}, {r['state']}",
            "phone": r["phone"] or "",
            "zip_code": r["zip"] or "",
            "source": "market_sweep",
            "ref": f"crm_{r['id']}",
        }
        try:
            res = EP.evaluate_lead(EVAL_BUYER, lead, "outcome")
        except Exception:
            res = {"grade": "D", "omega": 0.0, "price_usd": 0.0}
        g = res.get("grade", "D")
        grades[g] = grades.get(g, 0) + 1
        batch.append((g, float(res.get("omega", 0.0) or 0.0), r["id"]))
        graded += 1
        if write and len(batch) >= 50:
            c.executemany(
                "UPDATE crm_leads SET eval_grade=?, eval_omega=? WHERE id=?",
                batch,
            )
            c.commit()
            batch = []
    if write and batch:
        c.executemany(
            "UPDATE crm_leads SET eval_grade=?, eval_omega=? WHERE id=?", batch
        )
        c.commit()
    c.close()
    return {"graded": graded, "grades": grades,
            "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    res = main(write=True)
    print(json.dumps(res, indent=2))
    print(f"\nGraded {res['graded']} sweep leads | "
          f"A={res['grades']['A']} B={res['grades']['B']} "
          f"C={res['grades']['C']} D={res['grades']['D']}")
