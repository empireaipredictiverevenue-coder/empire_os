#!/usr/bin/env python3
"""expired_quote_reengage — Re-engage the top expired a2a_quotes with a fresh payment link.

For each expired a2a_quote above a size threshold we rebuild a BSC payment
URI pointing at the Empire OS vault and queue a re-engagement email through
the hub outbox (Brevo-flushed via mail_sender). We track every quote we touch
in si_quote_reengage so we never double-tap the same lead.

Usage:
    python3 expired_quote_reengage.py --limit 20
    python3 expired_quote_reengage.py --limit 20 --dry-run
    python3 expired_quote_reengage.py --limit 50 --min-amount 1000
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
HUB_URL = os.getenv("EMPIRE_HUB_URL", "http://127.0.0.1:8080")
VAULT = os.getenv(
    "BSC_WALLET_ADDRESS",
    "0x1339b487046B0ad924a10c20b1791608EA8595a8",
)
FROM_DISPLAY = "Empire OS <founder@empire-ai.co.uk>"

FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = FEEDBACK_DIR / "expired_reengage.jsonl"
TXT_REPORT = FEEDBACK_DIR / "expired_reengage_20260729.txt"


# ---------- DB helpers ----------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    return c


def ensure_reengage_table(c: sqlite3.Connection) -> None:
    """Track which quotes we've already re-engaged (idempotency guard)."""
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS si_quote_reengage (
            quote_id TEXT PRIMARY KEY,
            to_email TEXT,
            amount_usdc REAL,
            outbox_id INTEGER,
            status TEXT,
            sent_at TEXT
        )
        """
    )
    c.commit()


def top_expired(c: sqlite3.Connection, limit: int, min_amount: float):
    """Top-N expired quotes by amount, skipping any we've already re-engaged."""
    return c.execute(
        """
        SELECT q.quote_id, q.product, q.amount_usdc, q.buyer_wallet,
               q.expires_at, q.meta, q.signed_payload
          FROM a2a_quotes q
          LEFT JOIN si_quote_reengage r ON r.quote_id = q.quote_id
         WHERE q.status = 'expired'
           AND q.amount_usdc >= ?
           AND r.quote_id IS NULL
         ORDER BY q.amount_usdc DESC
         LIMIT ?
        """,
        (min_amount, limit),
    ).fetchall()


# ---------- email + payment link ----------

def extract_email(row) -> str | None:
    """Pull prospect_email from meta JSON, falling back to signed_payload."""
    raw_meta = row["meta"]
    if raw_meta:
        try:
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
            em = (meta.get("prospect_email") or meta.get("email")
                  or meta.get("to_email") or "").strip()
            if em and "@" in em:
                return em.lower()
        except Exception:
            pass
    raw_sp = row["signed_payload"]
    if raw_sp:
        try:
            sp = json.loads(raw_sp) if isinstance(raw_sp, str) else raw_sp
            for key in ("prospect_email", "email", "to_email",
                        "buyer_email", "contact_email"):
                em = (sp.get(key) or "").strip()
                if em and "@" in em:
                    return em.lower()
        except Exception:
            pass
    return None


def build_pay_url(quote_id: str, amount: float) -> str:
    """BSC pay URI — Vault + memo + amount in USDT."""
    amount_str = f"{amount:.2f}"
    return (
        f"bsc:{VAULT}"
        f"?memo=empire-os:{quote_id}:{amount_str}"
        f"&amount={amount_str}"
        f"&label=Empire%20OS%20Quote%20{quote_id}"
    )


def build_subject() -> str:
    return "Your Empire OS quote is still open"


def build_body(quote_id: str, product: str, amount: float, pay_url: str) -> str:
    new_expiry = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    return (
        f"Hi,\n\n"
        f"Your Empire OS quote {quote_id} for the {product} package "
        f"(${amount:,.2f} USDT) was set to expire, but we've kept the seat open "
        f"for you.\n\n"
        f"Pay here to activate it (single tap in any BSC wallet):\n"
        f"  {pay_url}\n\n"
        f"This extension is good through {new_expiry}. After that the quote "
        f"will be released back to the queue and another buyer may take the "
        f"slot.\n\n"
        f"If you'd like a different package, a payment plan, or want to walk "
        f"away — just reply to this email and we'll adjust or close the quote.\n\n"
        f"— {FROM_DISPLAY}\n"
        f"Empire OS\n"
    )


# ---------- hub outbox ----------

def enqueue(to_email: str, subject: str, body: str,
            lead_id: str, source: str) -> dict:
    payload = json.dumps({
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "lane": "a2a_reengage",
        "tier": "expired_revival",
        "lead_id": lead_id,
        "source": source,
    }).encode()
    req = urllib.request.Request(
        f"{HUB_URL}/v1/outbox/enqueue",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            return {"ok": True, **data}
    except urllib.error.HTTPError as e:
        body_b = e.read()[:200].decode("utf-8", "replace")
        return {"ok": False, "error": f"http_{e.code}", "body": body_b}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ---------- main ----------

def log_jsonl(record: dict) -> None:
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def run(limit: int, min_amount: float, dry_run: bool) -> dict:
    started = _now()
    summary = {
        "ts": started,
        "limit": limit,
        "min_amount": min_amount,
        "dry_run": dry_run,
        "vault": VAULT,
        "considered": 0,
        "no_email": 0,
        "queued": 0,
        "errors": 0,
        "total_amount_usdc": 0.0,
        "top": [],
        "error_samples": [],
    }
    c = db()
    try:
        ensure_reengage_table(c)
        rows = top_expired(c, limit, min_amount)
        summary["considered"] = len(rows)
        for r in rows:
            email = extract_email(r)
            top = {
                "quote_id": r["quote_id"],
                "product": r["product"],
                "amount_usdc": r["amount_usdc"],
                "to_email": email,
                "expires_at": r["expires_at"],
                "buyer_wallet": r["buyer_wallet"],
            }
            summary["top"].append(top)
            if not email:
                summary["no_email"] += 1
                log_jsonl({"ts": _now(), "quote_id": r["quote_id"],
                           "status": "skipped_no_email"})
                continue

            pay_url = build_pay_url(r["quote_id"], r["amount_usdc"])
            subject = build_subject()
            body = build_body(r["quote_id"], r["product"],
                              r["amount_usdc"], pay_url)

            if dry_run:
                summary["queued"] += 1
                summary["total_amount_usdc"] += float(r["amount_usdc"])
                log_jsonl({"ts": _now(), "quote_id": r["quote_id"],
                           "to_email": email, "amount_usdc": r["amount_usdc"],
                           "status": "dry_run", "pay_url": pay_url})
                continue

            resp = enqueue(email, subject, body, r["quote_id"], "quote_reengage")
            if resp.get("ok"):
                summary["queued"] += 1
                summary["total_amount_usdc"] += float(r["amount_usdc"])
                out_id = resp.get("id")
                c.execute(
                    """
                    INSERT OR REPLACE INTO si_quote_reengage
                        (quote_id, to_email, amount_usdc, outbox_id,
                         status, sent_at)
                    VALUES (?, ?, ?, ?, 'queued', ?)
                    """,
                    (r["quote_id"], email, r["amount_usdc"], out_id, _now()),
                )
                c.commit()
                log_jsonl({"ts": _now(), "quote_id": r["quote_id"],
                           "to_email": email, "amount_usdc": r["amount_usdc"],
                           "outbox_id": out_id, "status": "queued",
                           "pay_url": pay_url})
            else:
                summary["errors"] += 1
                if len(summary["error_samples"]) < 5:
                    summary["error_samples"].append(
                        {"quote_id": r["quote_id"], "resp": resp}
                    )
                log_jsonl({"ts": _now(), "quote_id": r["quote_id"],
                           "to_email": email, "amount_usdc": r["amount_usdc"],
                           "status": "error", "resp": resp})
    finally:
        c.close()
    summary["finished"] = _now()
    summary["total_amount_usdc"] = round(summary["total_amount_usdc"], 2)
    return summary


def write_report(summary: dict) -> None:
    """Write the human-readable report the task asks for."""
    lines = []
    lines.append("EXPIRED A2A QUOTE RE-ENGAGEMENT REPORT")
    lines.append(f"Date:           {summary['ts']}")
    lines.append(f"Vault:          {summary['vault']}")
    lines.append(f"Limit:          {summary['limit']}  "
                 f"Min amount: ${summary['min_amount']:.2f}")
    lines.append(f"Dry run:        {summary['dry_run']}")
    lines.append("")
    lines.append(f"Considered:     {summary['considered']}")
    lines.append(f"Queued:         {summary['queued']}")
    lines.append(f"Skipped (no email): {summary['no_email']}")
    lines.append(f"Errors:         {summary['errors']}")
    lines.append(f"Total re-engaged USD: ${summary['total_amount_usdc']:,.2f}")
    lines.append("")
    lines.append("TOP QUOTES BY AMOUNT:")
    lines.append(f"{'Rank':>4}  {'Quote ID':<18}  "
                 f"{'Product':<26}  {'Amount USD':>12}  "
                 f"{'To':<32}  {'Expires'}")
    lines.append("-" * 120)
    for i, q in enumerate(summary["top"], 1):
        lines.append(
            f"{i:>4}  {q['quote_id']:<18}  {q['product']:<26}  "
            f"${q['amount_usdc']:>10,.2f}  "
            f"{(q['to_email'] or '-'):<32}  "
            f"{(q['expires_at'] or '-')[:19]}"
        )
    if summary.get("error_samples"):
        lines.append("")
        lines.append("ERROR SAMPLES:")
        for e in summary["error_samples"]:
            lines.append(f"  {e['quote_id']}: {e['resp']}")
    lines.append("")
    lines.append("Note: emails are queued into si_outbox via "
                 "/v1/outbox/enqueue with source='quote_reengage'. "
                 "Mail-sender daemon flushes them through Brevo. "
                 "Verify with:")
    lines.append("  SELECT status, COUNT(*) FROM si_outbox "
                 "WHERE source='quote_reengage' GROUP BY status;")
    TXT_REPORT.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--min-amount", type=float, default=0.0,
                    help="Skip quotes below this USDT amount")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    summary = run(args.limit, args.min_amount, args.dry_run)
    write_report(summary)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("top", "error_samples")}, indent=2))
    print(f"\nReport: {TXT_REPORT}")
    print(f"JSONL:  {JSONL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
