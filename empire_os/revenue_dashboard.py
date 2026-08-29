"""Live revenue dashboard — brand colors, Recharts-ready JSON."""
import sqlite3, time, os
DB = "/root/empire_os/empire_os.db"

def build():
    c = sqlite3.connect(DB, timeout=8)
    # MRR from subscriptions
    sub = c.execute("SELECT plan, SUM(price_cents) FROM si_subscription WHERE status='active' GROUP BY plan").fetchall()
    # Seats
    seats = c.execute("SELECT count(*) FROM si_seat").fetchone()[0]
    # Settlements (revenue collected)
    settlements = c.execute("SELECT count(*), coalesce(sum(amount_cents),0) FROM si_settlements").fetchone()
    # Outbox pipeline (mail drain)
    out = {}
    for s in ("pay_nudge","enterprise_pilot","nurture_daemon","hub_loop_outreach"):
        out[s] = {
            "sent": c.execute("SELECT count(*) FROM si_outbox WHERE source=? AND status='sent'", (s,)).fetchone()[0],
            "pending": c.execute("SELECT count(*) FROM si_outbox WHERE source=? AND status='pending'", (s,)).fetchone()[0]
        }
    # Disaster multiplier status (hard-coded for demo; real: check NOAA/NWS)
    disaster = False  # no active event
    # Total MRR $
    mrr_cents = sum(price for _, price in sub) or 0
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "brand": {"navy":"#0a1628","gold":"#d4a843","slate":"#f4f5f7","accent":"#e8c97a"},
        "mrr_cents": mrr_cents,
        "mrr_usd": round(mrr_cents/100, 2),
        "subscriptions_by_plan": {plan: round(price/100,2) for plan,price in sub},
        "seats": seats,
        "settlement_count": settlements[0],
        "settlement_usd": round((settlements[1] or 0)/100,2),
        "outbox": out,
        "disaster_mode": disaster,
        "disaster_multiplier": 3 if disaster else 1,
        "pipeline_total_sent": c.execute("SELECT count(*) FROM si_outbox WHERE status='sent'").fetchone()[0],
        "pipeline_total_pending": c.execute("SELECT count(*) FROM si_outbox WHERE status='pending'").fetchone()[0],
    }
