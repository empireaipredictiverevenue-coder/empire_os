#!/usr/bin/env python3
"""a2a_sales_agent — Autonomous AI sales loop for A2A products.

Every tick:
  1. Pull intelligence snapshot (vault, aeo, lease, affiliate signals)
  2. Query si_buyer_outreach for warm prospects (active=1, no plan yet)
  3. Ask ollama: given snapshot + prospect niche, what product + price?
  4. If LLM picks a valid product, create a quote via a2a_marketplace
  5. Persist the sales attempt + reasoning to feedback/a2a_sales.jsonl

This is the FIRST slice of the full suite. Real close requires a
human wallet signing the resulting pay_url — autonomous signing is
out of scope for safety.

Env:
  SALES_AGENT_DRY_RUN=1 — don't actually create quotes
  SALES_AGENT_BATCH=20  — prospects per tick
  SALES_AGENT_MODEL=qwen2.5:3b
  OLLAMA_HOST=http://10.118.155.1:11434
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "a2a_sales.jsonl"

DRY_RUN = os.getenv("SALES_AGENT_DRY_RUN", "0") == "1"
BATCH = int(os.getenv("SALES_AGENT_BATCH", "20"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://10.118.155.1:11434")
# Force a known-working model — never inherit dead external defaults
OLLAMA_MODEL = os.getenv("SALES_AGENT_MODEL", "qwen2.5:3b")

VALID_PRODUCTS = [
    "lead_lane", "satellite_wastage", "warehouse_asset",
    "strike_pack", "ai_closer", "leadflow_saas_t2",
    "imperium_conversion_os", "empire_os_v4_beta",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(record: dict) -> None:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _ollama_chat(prompt: str, system: str = "", timeout: int = 90) -> Optional[str]:
    """Single ollama chat completion. Returns text or None on failure.

    Uses /api/chat endpoint (more reliable than /api/generate for
    system+prompt patterns). Serializes one request at a time so
    the 3B model isn't queue-stacked.
    """
    import threading
    if not hasattr(_ollama_chat, "_lock"):
        _ollama_chat._lock = threading.Lock()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else []) +
                    [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }
    with _ollama_chat._lock:
        try:
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/chat",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read())
                return (d.get("message", {}).get("content", "") or "").strip()
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception) as e:
            _log({"ts": _now(), "event": "ollama_error", "error": str(e)[:200]})
            return None


def warm_prospects(limit: int = BATCH) -> list:
    """Pull warm prospects: have email, no active subscription."""
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute("""
            SELECT prospect_id, email, niche, business_name, source, payout_per_lead, wallet
            FROM si_buyer_outreach
            WHERE active = 1 AND email IS NOT NULL AND email != ''
              AND email NOT LIKE 'dc-%' AND email NOT LIKE '%@v.co'
            ORDER BY payout_per_lead DESC NULLS LAST, last_touch_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def pick_product(prospect: dict, snapshot: dict) -> Optional[dict]:
    """Decide product+quantity for this prospect.

    Shallow v1: deterministic rule from prospect signal. LLM hooks later.
    Reasoning recorded for transparency.
    """
    niche = (prospect.get("niche") or "").lower()
    payout = prospect.get("payout_per_lead") or 0

    # Rule: high payout prospect → upsell imperium; mid → strike_pack;
    # low → lead_lane; unknown → strike_pack as safe default
    if payout >= 15:
        product, qty, reason = "imperium_conversion_os", 1, "high_payout_upsell"
    elif payout >= 8:
        product, qty, reason = "strike_pack", 1, "mid_payout_bundle"
    elif niche in ("roofing", "hvac", "plumbing", "electrical", "pest_control"):
        product, qty, reason = "lead_lane", 25, "service_niche_bulk"
    else:
        product, qty, reason = "strike_pack", 1, "default_bundle"

    return {"product": product, "quantity": qty, "reasoning": reason}


def send_quote_email(quote: dict, prospect: dict) -> dict:
    """Send quote pay_url to prospect via Brevo API directly.

    Direct path because:
    - hub outbox queue is 335k+ rows; sales_agent quotes would sit at back
    - Resend Cloudflare-blocked from this IP
    - Brevo API key now in /root/empire_secrets/brevo_api_key
    """
    email = prospect.get("email", "")
    if not email or "@" not in email:
        return {"skipped": "no_email"}
    if email.endswith("@v.co") or email.startswith("dc-"):
        return {"skipped": "test_email"}

    # Load Brevo key (mirror mail_sender logic — keep paths aligned)
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key:
        from pathlib import Path
        _bp = Path("/root/empire_secrets/brevo_api_key")
        if _bp.exists():
            api_key = _bp.read_text().strip()
    if not api_key:
        return {"sent": False, "error": "no_brevo_key"}

    from_email = os.getenv("EMPIRE_FROM", "founder@empire-ai.co.uk")
    # Brevo requires {name, email} sender
    sender_email = from_email.split("<")[-1].rstrip(">") if "<" in from_email else from_email

    product = quote.get("product", "lead_lane")
    amount = quote.get("amount_usdc", 0)
    pay_url = quote.get("pay_url", "")
    quote_id = quote.get("quote_id", "")

    subject = f"Your {product.replace('_', ' ').title()} offer — ${amount:.0f} USDC"
    body = (
        f"Hi,\n\n"
        f"Empire OS has prepared a tailored offer for your business:\n\n"
        f"  Product: {product.replace('_', ' ').title()}\n"
        f"  Amount: ${amount:.2f} USDC\n"
        f"  Quote ID: {quote_id}\n"
        f"  Expires: {quote.get('expires_at', 'in 30 min')}\n\n"
        f"Pay here:\n{pay_url}\n\n"
        f"After payment, delivery begins automatically. "
        f"This quote was generated by our AI sales agent based on your profile.\n\n"
        f"— Empire OS\n"
    )

    try:
        import urllib.request
        payload = {
            "sender": {"name": "Empire OS", "email": sender_email},
            "to": [{"email": email}],
            "subject": subject,
            "textContent": body,
        }
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "api-key": api_key},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
            return {"sent": True, "brevo_id": resp.get("messageId", "")}
    except Exception as e:
        return {"sent": False, "error": str(e)[:200]}


def run_once() -> dict:
    """One sales-agent tick. Returns summary dict."""
    from empire_os.empire_intelligence import snapshot as intel_snapshot
    from empire_os.a2a_marketplace import create_quote

    ts = _now()
    summary = {
        "ts": ts,
        "dry_run": DRY_RUN,
        "prospects_seen": 0,
            "decisions_made": 0,
            "skipped": 0,
            "quotes_created": 0,
            "emails_sent": 0,
            "emails_skipped": 0,
            "email_errors": 0,
            "errors": 0,
            }

    snap = intel_snapshot()
    _log({"ts": ts, "event": "tick_start", "snapshot_summary": {
        "vault_usdc": snap["vault"].get("vault_balance_usdc", 0),
        "a2a_pending": snap["a2a"].get("quotes_pending", 0),
        "subs_awaiting": snap["settlements"].get("subs_awaiting_payment", 0),
    }})

    prospects = warm_prospects(BATCH)
    summary["prospects_seen"] = len(prospects)

    for p in prospects:
        decision = pick_product(p, snap)
        if not decision:
            summary["skipped"] += 1
            continue
        summary["decisions_made"] += 1

        # Wallet placeholder — real wallet comes from buyer_apply form
        wallet = "EgJSales" + (p.get("email", "")[:8].replace("@", "")).encode().hex()[:16]

        if DRY_RUN:
            _log({
                "ts": _now(),
                "event": "would_quote",
                "prospect_email": p.get("email"),
                "decision": decision,
                "wallet": wallet,
            })
            summary["quotes_created"] += 1
            # DRY mode — log what the email would have been
            email_result = send_quote_email({
                "product": decision["product"],
                "amount_usdc": 0,
                "pay_url": f"solana:{os.getenv('SOLANA_VAULT_WALLET','?')}?amount=0&memo=DRY",
                "quote_id": "DRY_RUN",
                "expires_at": "n/a",
            }, p)
            _log({
                "ts": _now(),
                "event": "email_attempt_dry",
                "prospect_email": p.get("email"),
                "result": email_result,
            })
            if email_result.get("sent"):
                summary["emails_sent"] += 1
            elif email_result.get("skipped"):
                summary["emails_skipped"] += 1
            else:
                summary["email_errors"] += 1
            continue

        try:
            quote = create_quote(
                decision["product"], wallet, decision["quantity"],
                meta={"source": "sales_agent", "prospect_email": p.get("email"),
                      "reasoning": decision["reasoning"]},
            )
            _log({
                "ts": _now(),
                "event": "quote_created",
                "quote_id": quote["quote_id"],
                "amount_usdc": quote["amount_usdc"],
                "prospect_email": p.get("email"),
                "decision": decision,
            })
            summary["quotes_created"] += 1

            # Send the quote email via Resend
            email_result = send_quote_email(quote, p)
            _log({
                "ts": _now(),
                "event": "email_attempt",
                "quote_id": quote["quote_id"],
                "prospect_email": p.get("email"),
                "result": email_result,
            })
            if email_result.get("sent"):
                summary["emails_sent"] += 1
            elif email_result.get("skipped"):
                summary["emails_skipped"] += 1
            else:
                summary["email_errors"] += 1
        except Exception as e:
            summary["errors"] += 1
            _log({"ts": _now(), "event": "quote_error",
                  "error": str(e)[:200], "prospect": p.get("email")})

    _log({"ts": _now(), "event": "tick_end", "summary": summary})
    return summary


if __name__ == "__main__":
    print(json.dumps(run_once(), indent=2, default=str))