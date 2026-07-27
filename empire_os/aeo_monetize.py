#!/usr/bin/env python3
"""aeo_monetize — AEO page dynamic pricing + CTA injection + attribution.

Adds USDC price + per-request Solana Pay deeplink + ref-cookie attribution
to every AEO page served by hub.py at /aeo/{niche}/.

Tables:
  niche_pricing(niche TEXT PK, base_price_usdc REAL, multiplier REAL, updated_at)
  aeo_events(id, ts, niche, event_type, ref_code, ip_hash, ua_hash, value_cents)

Events: impression | click | conversion | refund

The hub calls render_aeo_page(niche, ref) instead of serving the static HTML.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
AEO_DIR = Path("/srv/aeo")

DEFAULT_PRICING = {
    "roofing": 14.0, "hvac": 12.0, "plumbing": 11.0, "electrical": 11.0,
    "pest_control": 8.0, "mass_torts": 22.0, "ai_automation": 18.0,
    "cybersecurity": 20.0, "lead_gen": 16.0, "marketing": 13.0,
    "real_estate": 15.0, "solar": 19.0, "general": 10.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_tables(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS niche_pricing (
            niche TEXT PRIMARY KEY,
            base_price_usdc REAL NOT NULL,
            multiplier REAL DEFAULT 1.0,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS aeo_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            niche TEXT NOT NULL,
            event_type TEXT NOT NULL,
            ref_code TEXT,
            ip_hash TEXT,
            ua_hash TEXT,
            value_cents INTEGER DEFAULT 0,
            meta TEXT
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_refs (
            code TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            commission_bps INTEGER DEFAULT 1000,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
    c.commit()


def seed_pricing(c: sqlite3.Connection) -> None:
    """Seed default prices if niche_pricing is empty."""
    count = c.execute("SELECT COUNT(*) FROM niche_pricing").fetchone()[0]
    if count > 0:
        return
    for niche, price in DEFAULT_PRICING.items():
        c.execute(
            "INSERT OR IGNORE INTO niche_pricing (niche, base_price_usdc) VALUES (?, ?)",
            (niche, price),
        )
    c.commit()


def get_price(c: sqlite3.Connection, niche: str) -> float:
    row = c.execute(
        "SELECT base_price_usdc, multiplier FROM niche_pricing WHERE niche = ?",
        (niche,),
    ).fetchone()
    if row:
        return round(row["base_price_usdc"] * row["multiplier"], 2)
    return DEFAULT_PRICING.get(niche, DEFAULT_PRICING["general"])


def get_or_create_ref(c: sqlite3.Connection, ref_code: str) -> Optional[dict]:
    """Look up affiliate ref. Returns None if unknown."""
    row = c.execute(
        "SELECT code, wallet, commission_bps FROM affiliate_refs WHERE code = ?",
        (ref_code,),
    ).fetchone()
    return dict(row) if row else None


def build_pay_url(niche: str, price_usdc: float, ref_code: Optional[str] = None) -> str:
    """Build a Solana Pay deeplink for the niche + price + ref."""
    vault = os.getenv("SOLANA_VAULT_WALLET", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
    memo = f"aeo:{niche}"
    if ref_code:
        memo += f":ref:{ref_code}"
    return (
        f"solana:{vault}"
        f"?amount={price_usdc:.2f}"
        f"&label=Empire%20OS%20{niche}"
        f"&memo={memo}"
    )


def log_event(c: sqlite3.Connection, niche: str, event_type: str,
              ref_code: Optional[str] = None,
              ip: Optional[str] = None, ua: Optional[str] = None,
              value_cents: int = 0, meta: Optional[dict] = None) -> None:
    c.execute(
        "INSERT INTO aeo_events (ts, niche, event_type, ref_code, ip_hash, ua_hash, value_cents, meta) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _now(), niche, event_type, ref_code,
            _hash(ip or ""), _hash(ua or ""),
            value_cents, json.dumps(meta) if meta else None,
        ),
    )
    c.commit()


def render_cta(niche: str, price_usdc: float, pay_url: str, ref_code: Optional[str] = None) -> str:
    """Return the dynamic CTA HTML block injected into AEO pages."""
    ref_note = f" <span style='opacity:.7'>(ref: {ref_code})</span>" if ref_code else ""
    return f"""
<div class="aeo-cta" style="background:#0a3d62;color:#fff;padding:1.5rem;border-radius:8px;margin:2rem 0;text-align:center">
  <h3 style="margin:0 0 .5rem">Get {niche.title()} Leads Delivered in USDC</h3>
  <p style="margin:0 0 1rem;opacity:.9">Pay per lead. Delivered to your CRM. Settled on Solana.</p>
  <p style="margin:0 0 1rem"><strong>${price_usdc:.2f} USDC / lead</strong>{ref_note}</p>
  <a href="{pay_url}" class="aeo-buy-btn"
     style="display:inline-block;background:#fff;color:#0a3d62;padding:.75rem 1.5rem;border-radius:4px;text-decoration:none;font-weight:600">
    Buy Leads Now →
  </a>
  <p style="margin:1rem 0 0;font-size:.85rem;opacity:.7">
    Or <a href="/v1/a2a/quote?product=lead_lane&niche={niche}" style="color:#fff;text-decoration:underline">request a custom quote</a>
  </p>
</div>
""".strip()


def render_page(niche: str, ref_code: Optional[str] = None) -> Tuple[str, int]:
    """Render an AEO page with dynamic CTA + tracking pixel."""
    html_path = AEO_DIR / niche / "index.html"
    if not html_path.exists():
        # Try to find by partial match
        matches = list(AEO_DIR.glob(f"**/{niche}/index.html"))
        if not matches:
            return f"<h1>Niche '{niche}' not found</h1>", 404
        html_path = matches[0]

    html = html_path.read_text()

    c = db()
    try:
        ensure_tables(c)
        seed_pricing(c)
        price = get_price(c, niche)
        pay_url = build_pay_url(niche, price, ref_code)
        cta = render_cta(niche, price, pay_url, ref_code)

        # Inject CTA right before </body>
        if "</body>" in html:
            html = html.replace("</body>", cta + "\n</body>")
        else:
            html += cta

        # Inject tracking pixel
        pixel = (
            f'<img src="/v1/aeo/track?event=impression&niche={niche}'
            f'{"&ref=" + ref_code if ref_code else ""}" '
            f'width="1" height="1" alt="" style="position:absolute">'
        )
        html = html.replace("</body>", pixel + "\n</body>")

        # Log the impression (deferred to avoid double-count if pixel hits)
        log_event(c, niche, "impression", ref_code=ref_code)
    finally:
        c.close()

    return html, 200


def conversion_report(days: int = 7) -> dict:
    c = db()
    try:
        ensure_tables(c)
        rows = c.execute("""
            SELECT niche, event_type, COUNT(*) as cnt, COALESCE(SUM(value_cents), 0) as value
            FROM aeo_events
            WHERE ts >= datetime('now', ?)
            GROUP BY niche, event_type
            ORDER BY niche, event_type
        """, (f"-{days} days",)).fetchall()
        summary = {}
        for r in rows:
            summary.setdefault(r["niche"], {})[r["event_type"]] = {
                "count": r["cnt"], "value_cents": r["value"],
            }
        return {"days": days, "by_niche": summary, "generated_at": _now()}
    finally:
        c.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        print(json.dumps(conversion_report(days), indent=2))
    else:
        print("usage: aeo_monetize.py report [days]")