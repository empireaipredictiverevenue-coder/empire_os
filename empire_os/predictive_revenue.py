#!/usr/bin/env python3
"""Empire OS — predictive revenue (forecast collections from the live pipeline).

No ML black box: a transparent funnel model built from REAL data we already
have. Inputs:
  - queued founder pay links (si_outbox source=seat_onboarding) -> $299 pipeline
  - historical nurture->pay conversion (from si_buyer_outreach touch/contact)
  - confirmed collections so far (si_ppc_invoices paid_at)
Outputs a 7/30-day collection forecast with a confidence band + the assumptions
used, so the number is auditable (not a hallucinated AGI figure).

Run: /root/venv/bin/python3 empire_os/predictive_revenue.py
"""
import sqlite3, sys, json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
FOUNDER_SEAT = 299.0  # USD, founder discount honored


def _c():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def forecast() -> dict:
    c = _c()
    now = datetime.now(timezone.utc)

    # --- pipeline: queued founder pay links ($299 each) ---
    queued = c.execute(
        "SELECT COUNT(*) FROM si_outbox WHERE source='seat_onboarding' "
        "AND status='pending'"
    ).fetchone()[0]
    pipeline_usd = queued * FOUNDER_SEAT

    # --- confirmed so far ---
    conf = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents),0)/100.0 "
        "FROM si_ppc_invoices WHERE paid_at IS NOT NULL"
    ).fetchone()
    confirmed_n, confirmed_usd = conf[0], conf[1]

    # --- nurture conversion baseline (real, from DB) ---
    st = dict(c.execute(
        "SELECT reply_state, COUNT(*) FROM si_buyer_outreach GROUP BY 1"
    ).fetchall())
    signups = sum(st.values())
    touched = c.execute(
        "SELECT COUNT(*) FROM si_buyer_outreach WHERE touch_count>0"
    ).fetchone()[0]
    # empirical open/click->pay proxy: use touch rate as a conservative
    # payment-intent proxy (confirmations will replace this once live).
    pay_intent = (touched / signups) if signups else 0.0

    # --- transparent model ---
    # assumption: queued links convert at pay_intent (conservative, no live
    # data yet) with a 14-day tail. Split across 7/30 day windows.
    conv_rate = max(pay_intent, 0.05)  # floor 5% so forecast isn't zero pre-data
    exp_7d = pipeline_usd * conv_rate * 0.4   # 40% of conversions land in 7d
    exp_30d = pipeline_usd * conv_rate
    band = 0.35  # +/-35% confidence band (no historical variance yet)

    c.close()
    return {
        "timestamp": now.isoformat(),
        "pipeline": {
            "queued_pay_links": queued,
            "founder_seat_usd": FOUNDER_SEAT,
            "pipeline_usd": round(pipeline_usd, 2),
        },
        "confirmed_to_date": {
            "count": confirmed_n,
            "usd": round(confirmed_usd, 2),
        },
        "assumptions": {
            "pay_intent_proxy": round(pay_intent, 4),
            "conv_rate_used": round(conv_rate, 4),
            "confidence_band": f"+/-{int(band*100)}%",
            "note": "conv_rate floored at 5% pre-live-payment data; "
                    "will tighten once solana_listener confirms real pays",
        },
        "forecast_collections_usd": {
            "next_7d_low": round(exp_7d * (1 - band), 2),
            "next_7d_exp": round(exp_7d, 2),
            "next_7d_high": round(exp_7d * (1 + band), 2),
            "next_30d_low": round(exp_30d * (1 - band), 2),
            "next_30d_exp": round(exp_30d, 2),
            "next_30d_high": round(exp_30d * (1 + band), 2),
        },
    }


if __name__ == "__main__":
    f = forecast()
    print(json.dumps(f, indent=2))
    fc = f["forecast_collections_usd"]
    print(f"\nPIPELINE ${f['pipeline']['pipeline_usd']:.0f} "
          f"({f['pipeline']['queued_pay_links']} queued links @ $299)")
    print(f"FORECAST collections: 7d ${fc['next_7d_exp']:.0f} "
          f"(±{int(0.35*100)}%) | 30d ${fc['next_30d_exp']:.0f}")
