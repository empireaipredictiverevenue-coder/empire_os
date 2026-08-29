"""Cash-buyer scoring tool.

Problem: si_buyer_outreach holds anyone who signed up — includes lookie-loos
who never pay. This tool separates REAL buyers with cash from tyre-kickers by
scoring on payment-capacity signals, not vanity signups.

Signals (all real, DB/on-chain):
  - paid_subs        : has an active/paid subscription (proven cash)
  - funded_quotes    : A2A quotes they funded (proven cash)
  - paid_leads       : leads delivered + billed to them (proven cash)
  - onchain_balance  : USDT in their wallet (proven cash, if known)
  - wallet_age_days  : older wallet = more serious
  - reply_state      : replied to outreach (engaged, not ghosting)
  - tier             : Omega classified tier (BRONZE..PLATINUM)
  - lookie_loo       : signed up, zero of above, never replied

Score 0-100. >=60 = REAL CASH BUYER. <30 = lookie-loo (suppress from paid sends).

Run:  python3 -m empire_os.cash_buyer_score            # report
      python3 -m empire_os.cash_buyer_score --tag      # write tier_cash to DB
      python3 -m empire_os.cash_buyer_score --real     # list only real buyers
"""
from __future__ import annotations
import sqlite3, argparse, json, sys
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def score_all() -> list[dict]:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    cols = {r[1] for r in c.execute("PRAGMA table_info(si_buyer_outreach)")}
    sel = ["prospect_id", "business_name", "email", "niche", "metro", "wallet",
           "payout_per_lead", "endpoint_url", "reply_state", "first_touch_at",
           "converted", "active"]
    sel = [s for s in sel if s in cols]
    buyers = c.execute(
        f"SELECT {','.join(sel)} FROM si_buyer_outreach"
    ).fetchall()
    for b in buyers:
        b = dict(b)
        pid = b["prospect_id"]
        score = 0
        reasons = []

        # proven cash: paid subscription
        paid_sub = c.execute(
            "SELECT COUNT(*) FROM si_subscription WHERE tenant_id=? AND status IN ('active','paid')",
            (pid,),
        ).fetchone()[0]
        if paid_sub:
            score += 35
            reasons.append("paid_sub")

        # proven cash: funded A2A quotes
        funded = c.execute(
            "SELECT COUNT(*) FROM a2a_quotes WHERE buyer_wallet=? AND status IN ('funded','released')",
            (b["wallet"],),
        ).fetchone()[0]
        if funded:
            score += 30
            reasons.append(f"funded_quotes:{funded}")

        # proven cash: billed leads
        billed = c.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM si_charges WHERE buyer_id=? AND status='succeeded'",
            (pid,),
        ).fetchone()[0]
        if billed:
            score += 20
            reasons.append(f"billed_leads:${billed/100:.0f}")

        # engaged: replied
        if (b["reply_state"] or "").lower() in ("replied", "interested", "positive"):
            score += 10
            reasons.append("replied")

        # omega tier
        tier = (b.get("classified_tier") or "").upper() if "classified_tier" in b else ""
        tier_pts = {"PLATINUM": 8, "GOLD": 6, "SILVER": 3, "BRONZE": 1}.get(tier, 0)
        if tier_pts:
            score += tier_pts
            reasons.append(f"tier:{tier}")

        # endpoint wired = serious intent to receive leads
        if b["endpoint_url"]:
            score += 5
            reasons.append("endpoint_wired")

        # lookie-loo penalty: signed up, never paid, never replied
        if score < 30 and (b["reply_state"] or "") == "contacted":
            score = max(score, 5)
            reasons.append("LOOKIE_LOO")

        score = min(score, 100)
        rows.append({
            "prospect_id": pid,
            "business": (b["business_name"] or "")[:40],
            "email": b["email"],
            "niche": b["niche"],
            "cash_score": score,
            "class": "REAL" if score >= 60 else ("WARM" if score >= 30 else "LOOKIE_LOO"),
            "reasons": ",".join(reasons),
        })
    c.close()
    rows.sort(key=lambda r: r["cash_score"], reverse=True)
    return rows


def tag_db(rows: list[dict]) -> int:
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS buyer_cash_score (
        prospect_id TEXT PRIMARY KEY, cash_score INT, cash_class TEXT,
        reasons TEXT, updated_at TEXT)""")
    for r in rows:
        c.execute(
            "INSERT OR REPLACE INTO buyer_cash_score VALUES (?,?,?,?,?)",
            (r["prospect_id"], r["cash_score"], r["class"], r["reasons"], _now()))
    c.commit()
    c.close()
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", action="store_true", help="write scores to DB")
    ap.add_argument("--real", action="store_true", help="only REAL cash buyers")
    a = ap.parse_args()
    rows = score_all()
    if a.real:
        rows = [r for r in rows if r["class"] == "REAL"]
    if a.tag:
        n = tag_db(rows)
        print(f"tagged {n} buyers -> buyer_cash_score")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
