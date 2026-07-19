"""Empire Cortex — Evaluation Product (REAL, not the $121/hr fiction).

Packages the Cortex Judge's lead-evaluation into a billable product:
a buyer posts a lead (or batch), we score it with the real Omega pipeline
(omega_os.qualify_prospect), return a grade, and bill USDC at a real
configurable price. No invented unit prices, no phantom payouts.

Real price model (set via env, sane B2B default):
  EVAL_PRICE_USD=0.50   # per lead scored (bulk-friendly)
Tiered later if needed. Settlement records to evaluation_ledger; the existing
USDC activation chain (solana_listener) collects payment against the invoice.
"""
from __future__ import annotations
import os
import time
import json
import sqlite3

PRICE_USD = float(os.environ.get("EVAL_PRICE_USD", "0.50"))


def _db():
    path = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
    c = sqlite3.connect(path, timeout=30)
    c.execute(
        """CREATE TABLE IF NOT EXISTS evaluation_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer TEXT,
            lead_ref TEXT,
            niche TEXT,
            omega REAL,
            grade TEXT,
            price_usd REAL,
            status TEXT DEFAULT 'billed',
            created_at TEXT
        )"""
    )
    return c


def grade_for(omega: float) -> str:
    """omega is 0-1 (total/100). Map to A/B/C/D."""
    if omega >= 0.75:
        return "A"
    if omega >= 0.55:
        return "B"
    if omega >= 0.35:
        return "C"
    return "D"


def evaluate_lead(buyer: str, lead: dict) -> dict:
    """Score one lead via the real Omega pipeline and bill it.

    lead keys: details, name, phone, zip_code, source, tort_key (optional)
    Returns the evaluation record (grade, omega, price, ledger id).
    """
    from empire_os import omega_os

    res = omega_os.qualify_prospect(
        backend=None,
        prospect_id=lead.get("ref") or f"eval_{int(time.time()*1000)}",
        tort_key=lead.get("tort_key"),
        details=lead.get("details", ""),
        source=lead.get("source", "eval_api"),
        name=lead.get("name", ""),
        phone=lead.get("phone", ""),
        zip_code=lead.get("zip_code", ""),
    )
    # OmegaScore.compute() returns total on a 0-100 scale + tier string.
    total = float(res.get("total", 0.0))
    omega = round(total / 100.0, 4)
    grade = grade_for(omega)
    c = _db()
    try:
        cur = c.execute(
            "INSERT INTO evaluation_ledger "
            "(buyer, lead_ref, niche, omega, grade, price_usd, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                buyer,
                lead.get("ref", ""),
                res.get("tort_key", "unknown"),
                omega,
                grade,
                PRICE_USD,
                "billed",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ),
        )
        lid = cur.lastrowid
        c.commit()
    finally:
        c.close()
    return {
        "ledger_id": lid,
        "buyer": buyer,
        "ref": lead.get("ref", ""),
        "omega": omega,
        "total_score": total,
        "tier": res.get("tier", "bronze"),
        "grade": grade,
        "price_usd": PRICE_USD,
        "status": "billed",
    }


def evaluate_batch(buyer: str, leads: list[dict]) -> dict:
    out = [evaluate_lead(buyer, l) for l in leads]
    return {
        "buyer": buyer,
        "count": len(out),
        "total_usd": round(sum(r["price_usd"] for r in out), 2),
        "grades": {g: sum(1 for r in out if r["grade"] == g) for g in ("A", "B", "C", "D")},
        "results": out,
    }


def ledger_total(buyer: str = None) -> float:
    c = _db()
    try:
        if buyer:
            return c.execute(
                "SELECT COALESCE(SUM(price_usd),0) FROM evaluation_ledger WHERE buyer=?",
                (buyer,),
            ).fetchone()[0]
        return c.execute("SELECT COALESCE(SUM(price_usd),0) FROM evaluation_ledger").fetchone()[0]
    finally:
        c.close()


if __name__ == "__main__":
    # smoke test (no network, real omega scoring on a dummy lead)
    r = evaluate_lead("smoke_test", {"ref": "smoke_1", "details": "roof repair Queens NY", "name": "Joe", "phone": "5551234", "zip_code": "11368"})
    print("SMOKE:", json.dumps(r))
    print("LEDGER TOTAL:", ledger_total())
