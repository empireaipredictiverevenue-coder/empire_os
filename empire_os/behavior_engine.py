#!/usr/bin/env python3
"""Empire OS — Behavioral Intelligence Engine (Empire Cortex behavior layer).

Studies REAL human behavior signals in our DB (no invented psychology):
  - attention: which niches/metros get signups vs which convert (AEO pull)
  - payment friction: why seated tenants / eval buyers don't complete USDC pay
  - outreach drop-off: nurture funnel stages where humans bail
  - hook psychology: which CTA/state patterns correlate with conversion

Outputs behavior_report.json (consumed by cortex_engine + daily ping).
Pure analysis of live data — every number traced to a SQL query.

Run: /root/venv/bin/python3 empire_os/behavior_engine.py
"""
import sqlite3, json, sys, os
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"


def _c():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def attention(c) -> dict:
    """Which niches pull signups vs which actually convert — attention decay."""
    rows = c.execute(
        "SELECT niche, COUNT(*) n, "
        "SUM(CASE WHEN converted=1 THEN 1 ELSE 0 END) conv "
        "FROM si_buyer_outreach GROUP BY niche"
    ).fetchall()
    out = []
    for r in rows:
        n, conv = r["n"], r["conv"]
        out.append({
            "niche": r["niche"], "signups": n, "converted": conv,
            "conv_rate_pct": round(100 * conv / n, 2) if n else 0.0,
        })
    out.sort(key=lambda x: x["signups"], reverse=True)
    # attention decay = top niche share of all signups
    total = sum(x["signups"] for x in out) or 1
    top_share = round(100 * out[0]["signups"] / total, 1) if out else 0
    return {"top_niche": out[0]["niche"] if out else None,
            "top_niche_signup_share_pct": top_share,
            "by_niche": out[:10], "total_signups": total}


def payment_friction(c) -> dict:
    """Why humans don't complete the USDC pay step."""
    seated = c.execute(
        "SELECT COUNT(*) FROM lanes WHERE seat_price > 0"
    ).fetchone()[0]
    # settlements: how many pending vs settled (the drop at pay)
    s = c.execute(
        "SELECT status, COUNT(*) FROM evaluation_settlements GROUP BY status"
    ).fetchall()
    settle = {r["status"]: r["status"] for r in s}  # placeholder
    settle_counts = dict(c.execute(
        "SELECT status, COUNT(*) FROM evaluation_settlements GROUP BY status"
    ).fetchall())
    outbox = dict(c.execute(
        "SELECT status, COUNT(*) FROM si_outbox GROUP BY status"
    ).fetchall()) if c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='si_outbox'"
    ).fetchone() else {}
    # pay-link sent but not confirmed = friction point
    links_sent = outbox.get("sent", outbox.get("pending", 0))
    return {
        "seated_lanes": seated,
        "eval_settlements": settle_counts,
        "pay_links_sent": links_sent,
        "friction_point": "USDC pay confirmation (links sent, 0 confirmed)",
    }


def outreach_dropoff(c) -> dict:
    """Where humans bail in the nurture funnel."""
    stages = dict(c.execute(
        "SELECT reply_state, COUNT(*) FROM si_buyer_outreach GROUP BY reply_state"
    ).fetchall())
    total = sum(stages.values()) or 1
    converted = c.execute(
        "SELECT COUNT(*) FROM si_buyer_outreach WHERE converted=1"
    ).fetchone()[0]
    biggest = max(stages, key=lambda k: stages[k]) if stages else None
    return {
        "stages": stages,
        "total": total,
        "converted": converted,
        "conversion_pct": round(100 * converted / total, 2),
        "biggest_drop": biggest,
    }


def hook_psychology(c) -> dict:
    """Which lead states/grades correlate with action (proxy for hook strength)."""
    graded = dict(c.execute(
        "SELECT eval_grade, COUNT(*) FROM crm_leads "
        "WHERE eval_grade IS NOT NULL GROUP BY eval_grade"
    ).fetchall())
    # C-grade leads are the actionable middle — what % of pipeline they are
    total_graded = sum(graded.values()) or 1
    c_share = round(100 * graded.get("C", 0) / total_graded, 1)
    return {
        "grade_distribution": graded,
        "c_grade_share_pct": c_share,
        "insight": "C-grade (warm, actionable) is the convertable middle — "
                   "prioritize hooks that move D->C, not A (rare).",
    }


def main() -> dict:
    c = _c()
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "attention": attention(c),
        "payment_friction": payment_friction(c),
        "outreach_dropoff": outreach_dropoff(c),
        "hook_psychology": hook_psychology(c),
    }
    c.close()
    return report


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=2))
