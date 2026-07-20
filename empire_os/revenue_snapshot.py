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

    # --- funnel conversion rates (where the leaks are) ---
    signups = funnel["total_signups"]
    touched = funnel["touched_total"]
    contacted = funnel["contacted"]
    converted = c.execute(
        "SELECT COUNT(*) FROM si_buyer_outreach WHERE converted=1").fetchone()[0]
    nurture_conv = round(contacted / touched * 100, 2) if touched else 0.0
    signup_conv = round(converted / signups * 100, 4) if signups else 0.0
    collection_rate = round(paid_usd / total_billed * 100, 2) if total_billed else 0.0

    funnels = {
        "nurture": {
            "signups": signups, "touched": touched, "contacted": contacted,
            "converted": converted,
            "touch_rate_pct": round(touched / signups * 100, 2) if signups else 0.0,
            "contact_rate_pct": nurture_conv,
            "signup_to_buyer_pct": signup_conv,
        },
        "collections": {
            "billed_usd": round(total_billed, 2),
            "collected_usd": round(paid_usd, 2),
            "collection_rate_pct": collection_rate,
        },
    }

    # --- threshold alerts (flag stalls so the ping drives action) ---
    alerts = []
    if collection_rate == 0 and total_billed > 0:
        alerts.append(f"LEAK: 0% of ${total_billed:.0f} billed collected (invoices open, none paid)")
    if signup_conv == 0:
        alerts.append(f"LEAK: 0% signup->buyer conversion ({converted} converted of {signups} signups)")
    if touched / signups < 0.05 and signups > 1000:
        alerts.append(f"LEAK: nurture touch rate {touched/signups*100:.1f}% (only {touched} of {signups} contacted)")
    if seated[0] < 50:
        alerts.append(f"CAPACITY: only {seated[0]} seated lanes (revenue ceiling low)")

    # --- payment confirmations (solana_listener marks paid_at on-chain) ---
    paid_rows = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents),0), MAX(paid_at) "
        "FROM si_ppc_invoices WHERE paid_at IS NOT NULL").fetchone()
    conf = {
        "confirmed_count": paid_rows[0],
        "confirmed_usd": round((paid_rows[1] or 0) / 100, 2),
        "last_confirmed_at": paid_rows[2],
    }
    seat_conf = c.execute(
        "SELECT COUNT(*) FROM si_subscription WHERE status='active' "
        "AND payment_ref != ''").fetchone()[0]
    conf["seats_activated"] = seat_conf
    try:
        import subprocess
        out = subprocess.run(["pgrep", "-f", "solana_listener"],
                             capture_output=True, text=True, timeout=5)
        conf["listener_active"] = bool(out.stdout.strip())
    except Exception:
        conf["listener_active"] = False

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
        "payments": conf,
        "nurture_funnel": funnel,
        "funnels": funnels,
        "outbound_campaigns": campaigns,
        "outbound_audience_total": total_audience,
        "seated_lanes": seats,
        "alerts": alerts,
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
    p = s["payments"]
    last = p["last_confirmed_at"] or "never"
    print(f"Payments: {p['confirmed_count']} confirmed (${p['confirmed_usd']:.2f}) | "
          f"seats activated: {p['seats_activated']} | listener: "
          f"{'UP' if p['listener_active'] else 'DOWN'} | last: {last[:19]}")
    fn = s["funnels"]
    print(f"Conv: nurture contact {fn['nurture']['contact_rate_pct']}% | "
          f"signup->buyer {fn['nurture']['signup_to_buyer_pct']}% | "
          f"collection {fn['collections']['collection_rate_pct']}%")
    if s["alerts"]:
        print("\n!!! ALERTS:")
        for a in s["alerts"]:
            print(f"  - {a}")
