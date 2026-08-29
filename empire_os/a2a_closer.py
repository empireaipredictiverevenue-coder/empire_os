#!/usr/bin/env python3
"""a2a_closer — Autonomous closing loop for A2A marketplace quotes.

Pipeline (each tick):
  1. Pull pending quotes whose pay_url was never delivered -> send via hub outbox.
  2. Poll funded quotes awaiting delivery -> provision seat + release_escrow.
  3. Nudge expired/unfunded quotes (LLM picks retry copy or downsell).
  4. Self-learn: record outcome per quote -> feedback/a2a_closer.jsonl.

LLM brain (optional): ollama qwen2.5:3b drafts close/nudge copy and
decides retry vs downsell. Falls back to rule-based templates if ollama down.

Env:
  CLOSER_DRY_RUN=1      don't send / release (inspect only)
  CLOSER_INTERVAL=120   seconds between ticks
  CLOSER_BATCH=25       quotes per tick
  CLOSER_MODEL=qwen2.5:3b
  OLLAMA_HOST=http://10.118.155.1:11434
  HUB_URL=http://127.0.0.1:8081
"""
from __future__ import annotations
import os
import json
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, "/root/empire_os")
from empire_os.a2a_marketplace import (
    db, ensure_tables, get_quote, fund_quote, release_escrow,
    refund_escrow, list_quotes,
)

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8081")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "a2a_closer.jsonl"
LEARN_PATH = FEEDBACK_DIR / "a2a_closer_learn.jsonl"

DRY_RUN = os.getenv("CLOSER_DRY_RUN", "0") == "1"
INTERVAL = int(os.getenv("CLOSER_INTERVAL", "120"))
BATCH = int(os.getenv("CLOSER_BATCH", "25"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://10.118.155.1:11434")
OLLAMA_MODEL = os.getenv("CLOSER_MODEL", "qwen2.5:3b")

# Which buyer contacts get the pay_url. Marketplace stores buyer_wallet only;
# we resolve email via si_buyer_outreach (same table a2a_sales_agent uses).
def _log(ev: dict) -> None:
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(ev) + "\n")
    except Exception:
        pass

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ollama(prompt: str, system: str = "You are a concise B2B closing assistant.") -> Optional[str]:
    import urllib.request
    import urllib.error
    try:
        body = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"num_predict": 160, "temperature": 0.5},
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode()).get("response", "").strip()
    except Exception as e:
        _log({"t": _now(), "ev": "ollama_fail", "err": str(e)[:120]})
        return None

def _buyer_contact(quote: dict) -> Optional[dict]:
    """Resolve email + name for a quote. Prefer meta.prospect_email
    (set by a2a_sales_agent); fall back to si_buyer_outreach by wallet."""
    import json as _json
    meta = quote.get("meta")
    email = None
    if meta:
        try:
            m = _json.loads(meta) if isinstance(meta, str) else meta
            email = m.get("prospect_email")
        except Exception:
            email = None
    if email:
        return {"email": email, "name": email.split("@")[0].replace(".", " ").title()}
    c = db()
    try:
        w = quote.get("buyer_wallet", "")
        row = c.execute(
            "SELECT email, business_name FROM si_buyer_outreach WHERE wallet=? LIMIT 1", (w,)
        ).fetchone()
        if row:
            return {"email": row["email"], "name": (row["business_name"] or "Buyer")}
        return None
    except Exception:
        return None
    finally:
        try: c.close()
        except Exception: pass

def _pay_url_for(quote: dict) -> str:
    """Reconstruct the vault pay_url from stored quote fields."""
    if quote.get("pay_url"):
        return quote["pay_url"]
    from empire_os.a2a_marketplace import VAULT_WALLET
    qid = quote["quote_id"]
    amt = float(quote.get("amount_usdc", 0))
    prod = quote.get("product", "product")
    memo = f"a2a:{qid}"
    return (f"bsc:{VAULT_WALLET}"
            f"?amount={amt:.2f}"
            f"&label=Empire%20A2A%20{prod}"
            f"&memo={memo}")

def _send_pay_url(quote: dict) -> bool:
    """Send the pay_url to the buyer via hub outbox (Brevo)."""
    quote = dict(quote)
    quote["pay_url"] = _pay_url_for(quote)
    quote["memo"] = f"a2a:{quote['quote_id']}"
    contact = _buyer_contact(quote)
    email = contact.get("email") if contact else None
    name = contact.get("name", "Buyer") if contact else "Buyer"
    if not email:
        _log({"t": _now(), "ev": "no_contact", "quote": quote["quote_id"]})
        return False
    subject = f"Your Empire A2A {quote['product']} access — one step from live"
    copy = _ollama(
        f"Write a 3-sentence relationship-first reminder for product {quote['product']} "
        f"priced {quote['amount_usdc']} USDT. Buyer name {name}. Say access is one tap away "
        f"on their activation page — do NOT paste a wallet address.",
        system="Concise B2B payment reminder, no fluff, max 60 words."
    ) or (
        f"Hi {name}, your {quote['product']} access is one tap away. "
        f"Open your activation page to fund and go live instantly."
    )
    try:
        from empire_os.templates.email.email_helpers import wrap, pay_link
        plink = pay_link(quote["memo"], float(quote["amount_usdc"]))
        inner = (f"<p>{copy}</p>"
                 f"<p style='margin:18px 0'><a href='{plink}' "
                 f"style='background:#39ff88;color:#050810;padding:12px 20px;"
                 f"border-radius:10px;font-weight:700;text-decoration:none'>"
                 f"Open activation page</a></p>"
                 f"<p style='color:#9bb0c9;font-size:13px'>Memo: {quote['memo']}</p>")
        html = wrap(subject, "Your A2A access is one tap away", inner, email)
    except Exception:
        html = f"<p>{copy}</p><p><b>Activate:</b> {quote['pay_url']}</p>"
    payload = {
        "to": email,
        "subject": subject,
        "html": html,
        "tags": ["a2a", "closer", quote["product"]],
    }
    if DRY_RUN:
        _log({"t": _now(), "ev": "send_dryrun", "to": email, "quote": quote["quote_id"]})
        return True
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{HUB_URL}/v1/outbox/enqueue",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            ok = r.status == 200
            _log({"t": _now(), "ev": "send", "to": email, "quote": quote["quote_id"], "ok": ok})
            return ok
    except Exception as e:
        _log({"t": _now(), "ev": "send_fail", "quote": quote["quote_id"], "err": str(e)[:120]})
        return False

def _nudge(quote: dict) -> None:
    """LLM decides retry copy or downsell; send nudge via outbox."""
    contact = _buyer_contact(quote)
    email = contact.get("email") if contact else None
    if not email:
        return
    decision = _ollama(
        f"Buyer for {quote['product']} ({quote['amount_usdc']} USDT) has not paid in 24h. "
        f"Options: (A) retry same offer, (B) downsell to cheaper tier. Reply A or B with one line.",
        system="You decide retry vs downsell for a stalled B2B deal. One word A/B then reason."
    ) or "A"
    downsell = decision.strip().upper().startswith("B")
    copy = (f"We can offer a lighter tier if {quote['amount_usdc']} USDT is steep — "
            f"reply 'lite'." if downsell else
            f"Friendly nudge: your {quote['product']} access is one payment away.")
    if DRY_RUN:
        _log({"t": _now(), "ev": "nudge_dryrun", "quote": quote["quote_id"], "downsell": downsell})
        return
    try:
        import urllib.request
        payload = {
            "to": email,
            "subject": f"Still interested in {quote['product']}?",
            "html": f"<p>{copy}</p><p><b>Pay:</b> {quote['pay_url']}</p>",
            "tags": ["a2a", "nudge", quote["product"]],
        }
        req = urllib.request.Request(
            f"{HUB_URL}/v1/outbox/enqueue", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            _log({"t": _now(), "ev": "nudge", "quote": quote["quote_id"],
                  "downsell": downsell, "ok": r.status == 200})
    except Exception as e:
        _log({"t": _now(), "ev": "nudge_fail", "quote": quote["quote_id"], "err": str(e)[:120]})

def _learn(quote_id: str, step: str, result: str) -> None:
    """Append outcome to learn log for later strategy tuning."""
    try:
        with open(LEARN_PATH, "a") as f:
            f.write(json.dumps({"t": _now(), "quote": quote_id, "step": step,
                                 "result": result}) + "\n")
    except Exception:
        pass

def tick() -> dict:
    c = db()
    try:
        ensure_tables(c)
        stats = {"sent": 0, "released": 0, "nudged": 0, "refunded": 0, "pending": 0}
        # 1) pending -> deliver pay_url (only once: track via a2a_escrow.delivery_proof NULL)
        pending = c.execute(
            "SELECT * FROM a2a_quotes WHERE status='pending' "
            "AND quote_id NOT IN (SELECT quote_id FROM a2a_escrow WHERE delivery_proof='sent') "
            "ORDER BY created_at DESC LIMIT ?", (BATCH,)
        ).fetchall()
        stats["pending"] = len(pending)
        for q in pending:
            qd = dict(q)
            if _send_pay_url(qd):
                c.execute("UPDATE a2a_escrow SET delivery_proof='sent' WHERE quote_id=?",
                          (qd["quote_id"],))
                c.commit()
                stats["sent"] += 1
                _learn(qd["quote_id"], "send", "ok")
        # 2) funded -> release (delivery proof = seat provisioned)
        funded = list_quotes(limit=BATCH, status="funded")
        for q in funded:
            res = release_escrow(q["quote_id"], delivery_proof=f"auto_close:{_now()}")
            if res.get("ok"):
                stats["released"] += 1
                _learn(q["quote_id"], "release", "ok")
                _log({"t": _now(), "ev": "released", "quote": q["quote_id"],
                      "seat": res.get("seat_id")})
        # 3) expired/unfunded -> nudge (status still pending but past expiry handled upstream)
        expired = c.execute(
            "SELECT * FROM a2a_quotes WHERE status='pending' AND expires_at < ? "
            "ORDER BY created_at DESC LIMIT ?", (_now(), BATCH)
        ).fetchall()
        for q in expired:
            c.execute("UPDATE a2a_quotes SET status='expired' WHERE quote_id=?",
                      (q["quote_id"],))
            c.commit()
            _nudge(dict(q))
            stats["nudged"] += 1
            _learn(q["quote_id"], "nudge", "expired")
        return stats
    finally:
        c.close()

def main() -> None:
    print(f"[a2a_closer] dry_run={DRY_RUN} interval={INTERVAL}s batch={BATCH}")
    while True:
        try:
            stats = tick()
            print(f"[a2a_closer] {_now()} {json.dumps(stats)}")
        except Exception as e:
            print(f"[a2a_closer] tick error: {e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
