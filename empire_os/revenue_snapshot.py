#!/usr/bin/env python3
"""Empire OS — revenue snapshot (reads the tables that ACTUALLY hold money).

The legacy revenue_dashboard.py reads si_settlements / si_charges which are
empty; real revenue lives in si_ppc_invoices (PPL invoices billed per delivered
lead) + the nurture funnel in si_buyer_outreach + outbound_campaigns audiences.

Outputs a compact JSON snapshot + prints a human summary. Designed to be cron'd
(Telegram delivery handled by the cron wrapper, not here).

Run inside the container: /root/venv/bin/python3 empire_os/revenue_snapshot.py
"""
import sqlite3, json, sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"


def _c():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def snapshot() -> dict:
    c = _c()
    now = datetime.now(timezone.utc).isoformat()

    # --- PPL invoicing (real revenue engine) ---
    inv = c.execute(
        "SELECT status, COUNT(*) n, COALESCE(SUM(amount_cents),0) cents "
        "FROM si_ppc_invoices GROUP BY status"
    ).fetchall()
    inv_by = {r["status"]: {"count": r["n"], "usd": r["cents"] / 100} for r in inv}
    total_billed = sum(v["usd"] for v in inv_by.values())
    open_usd = inv_by.get("open", {}).get("usd", 0.0)
    paid_usd = inv_by.get("paid", {}).get("usd", 0.0) + inv_by.get("settled", {}).get("usd", 0.0)

    # per-buyer billed
    per_buyer = c.execute(
        "SELECT buyer_id, COUNT(*) n, COALESCE(SUM(amount_cents),0) cents "
        "FROM si_ppc_invoices GROUP BY buyer_id ORDER BY cents DESC"
    ).fetchall()
    buyers = [{"buyer_id": r["buyer_id"][:8], "invoices": r["n"],
               "billed_usd": r["cents"] / 100} for r in per_buyer]

    # --- nurture funnel (inbound AEO signups) ---
    st = dict(c.execute(
        "SELECT reply_state, COUNT(*) FROM si_buyer_outreach GROUP BY 1").fetchall())
    touched = c.execute(
        "SELECT COUNT(*) FROM si_buyer_outreach WHERE touch_count>0").fetchone()[0]
    funnel = {
        "total_signups": sum(st.values()),
        "cold": st.get("cold", 0),
        "contacted": st.get("contacted", 0),
        "touched_total": touched,
        "failed_recovered": st.get("outreach_failed", 0),
    }

    # --- outbound campaigns ---
    camps = c.execute(
        "SELECT name, status, audience_size, sent FROM outbound_campaigns").fetchall()
    campaigns = [{"name": r["name"], "status": r["status"],
                  "audience": r["audience_size"], "sent": r["sent"]}
                 for r in camps]
    total_audience = sum(r["audience_size"] for r in camps)

    # --- seated lanes (revenue capacity) ---
    seated = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(seat_price),0) FROM lanes "
        "WHERE occupied_by IS NOT NULL AND occupied_by != ''").fetchall()[0]
    seats = {"seated_lanes": seated[0], "seat_value_usd": seated[1]}

    c.close()
    return {
        "timestamp": now,
        "revenue": {
            "total_billed_usd": round(total_billed, 2),
            "open_usd": round(open_usd, 2),
            "collected_usd": round(paid_usd, 2),
            "by_status": inv_by,
            "per_buyer": buyers,
        },
        "nurture_funnel": funnel,
        "outbound_campaigns": campaigns,
        "outbound_audience_total": total_audience,
        "seated_lanes": seats,
    }


if __name__ == "__main__":
    s = snapshot()
    print(json.dumps(s, indent=2))
    # one-line summary for cron/telegram
    r = s["revenue"]
    print(f"\n=== SUMMARY {s['timestamp'][:10]} ===")
    print(f"Billed ${r['total_billed_usd']:.2f} | Open ${r['open_usd']:.2f} | "
          f"Collected ${r['collected_usd']:.2f}")
    print(f"Nurture: {s['nurture_funnel']['total_signups']} signups, "
          f"{s['nurture_funnel']['touched_total']} touched, "
          f"{s['nurture_funnel']['contacted']} contacted")
    print(f"Outbound: {len(s['outbound_campaigns'])} campaigns, "
          f"{s['outbound_audience_total']} audience | "
          f"Seated lanes: {s['seated_lanes']['seated_lanes']}")
