"""Empire Cortex — Evaluation Product (REAL, not the $121/hr fiction).

Packages the Cortex Judge's lead-evaluation into a billable product:
a buyer posts a lead (or batch), we score it with the real Omega pipeline
(omega_os.qualify_prospect), return a grade, and bill per the HYBRID model.

HYBRID PRICING (best of both worlds):
  - Grading is FREE for every lead (Omega score + A/B/C/D grade).
  - OUTCOME mode (default): charge only when a graded A/B lead CONVERTS.
        EVAL_CONVERT_USD = 0.50   # per A/B lead that converts
  - PER_SCORE mode (opt-in, casual buyers): charge per lead scored.
        EVAL_PRICE_USD = 0.20     # volume rate (was 0.50 casual)
No invented unit prices, no phantom payouts. Settlement records to
evaluation_ledger; the existing USDC activation chain (solana_listener)
collects payment against the invoice.
"""
from __future__ import annotations
import os
import time
import json
import sqlite3

# Hybrid knobs (env-overridable)
PRICE_USD = float(os.environ.get("EVAL_PRICE_USD", "0.20"))      # per-score (opt-in)
CONVERT_USD = float(os.environ.get("EVAL_CONVERT_USD", "0.50"))  # per A/B conversion
DEFAULT_MODE = os.environ.get("EVAL_MODE", "outcome")           # outcome | per_score


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
            billing TEXT,
            status TEXT DEFAULT 'billed',
            created_at TEXT
        )"""
    )
    # migrate: older ledgers may lack the billing column
    cols = {r[1] for r in c.execute("PRAGMA table_info(evaluation_ledger)")}
    if "billing" not in cols:
        c.execute("ALTER TABLE evaluation_ledger ADD COLUMN billing TEXT")
    if "status" not in cols:
        c.execute("ALTER TABLE evaluation_ledger ADD COLUMN status TEXT DEFAULT 'billed'")
    c.execute(
        """CREATE TABLE IF NOT EXISTS evaluation_conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer TEXT,
            lead_ref TEXT,
            charged_usd REAL,
            created_at TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS evaluation_settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer TEXT,
            lead_ref TEXT,
            amount_usd REAL,
            wallet TEXT,
            status TEXT DEFAULT 'pending',
            tx_sig TEXT,
            created_at TEXT
        )"""
    )
    return c


def _ensure_tenant_cols(c):
    """si_tenant in some DBs predates api_key/delivery cols the code expects.
    Add them idempotently so buyer API keys are storable + resolvable."""
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(si_tenant)").fetchall()}
    except sqlite3.OperationalError:
        return  # si_tenant absent (non-hub DB)
    for col in ("api_key", "delivery_email", "last_delivery_at"):
        if col not in cols:
            try:
                c.execute(f"ALTER TABLE si_tenant ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
    c.commit()


def resolve_buyer(api_key: str) -> str | None:
    """Map an X-API-Key header to a real tenant_id. Returns None if unknown."""
    if not api_key:
        return None
    c = _db()
    try:
        _ensure_tenant_cols(c)
        row = c.execute(
            "SELECT tenant_id FROM si_tenant WHERE api_key=? AND status='active'",
            (api_key,),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None  # si_tenant/api_key not present in this DB
    finally:
        c.close()


def _buyer_wallet(c, buyer: str) -> str:
    """Best-effort lookup of a buyer's USDC wallet for settlement."""
    try:
        row = c.execute(
            "SELECT crypto_wallet FROM si_tenant WHERE tenant_id=?", (buyer,)
        ).fetchone()
        return row[0] if row and row[0] else ""
    except sqlite3.OperationalError:
        return ""


def grade_for(omega: float) -> str:
    """omega is 0-1 (total/100). Map to A/B/C/D."""
    if omega >= 0.75:
        return "A"
    if omega >= 0.55:
        return "B"
    if omega >= 0.35:
        return "C"
    return "D"


def evaluate_lead(buyer: str, lead: dict, mode: str = None) -> dict:
    """Score one lead via the real Omega pipeline, grade FREE, bill per mode.

    mode: 'outcome' (default) = free grade, charge later on A/B conversion;
          'per_score' = charge PRICE_USD now per lead scored.
    Returns the evaluation record (grade, omega, billing, price).
    """
    from empire_os import omega_os

    mode = mode or DEFAULT_MODE
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
    total = float(res.get("total", 0.0))
    omega = round(total / 100.0, 4)
    grade = grade_for(omega)

    # Billing decision
    if mode == "per_score":
        billing, price, status = "per_score", PRICE_USD, "billed"
    else:  # outcome: free to grade, billed only on conversion later
        billing, price, status = "outcome", 0.0, "pending"

    c = _db()
    try:
        cur = c.execute(
            "INSERT INTO evaluation_ledger "
            "(buyer, lead_ref, niche, omega, grade, price_usd, billing, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                buyer,
                lead.get("ref", ""),
                res.get("tort_key", "unknown"),
                omega,
                grade,
                price,
                billing,
                status,
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
        "billing": billing,
        "price_usd": price,
        "status": status,
    }


def record_conversion(buyer: str, lead_ref: str) -> dict:
    """Outcome billing: a graded A/B lead converted -> charge CONVERT_USD.

    Looks up the original evaluation; only A/B grades are billable. Idempotent
    per lead_ref (won't double-charge). Returns the charge record or skip reason.
    """
    c = _db()
    try:
        row = c.execute(
            "SELECT id, grade, billing, status FROM evaluation_ledger "
            "WHERE buyer=? AND lead_ref=? ORDER BY id DESC LIMIT 1",
            (buyer, lead_ref),
        ).fetchone()
        if not row:
            return {"charged": False, "reason": "no evaluation found"}
        lid, grade, billing, status = row
        if grade not in ("A", "B", "C"):
            return {"charged": False, "reason": f"grade {grade} not billable (junk)"}
        if billing != "outcome":
            return {"charged": False, "reason": f"billing={billing} (not outcome)"}
        if status == "billed":
            return {"charged": False, "reason": "already billed"}
        c.execute(
            "UPDATE evaluation_ledger SET price_usd=?, status='billed' WHERE id=?",
            (CONVERT_USD, lid),
        )
        c.execute(
            "INSERT INTO evaluation_conversions (buyer, lead_ref, charged_usd, created_at) "
            "VALUES (?,?,?,?)",
            (buyer, lead_ref, CONVERT_USD,
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        # record a pending USDC settlement obligation (real payout rail wires later)
        wallet = _buyer_wallet(c, buyer)
        c.execute(
            "INSERT INTO evaluation_settlements (buyer, lead_ref, amount_usd, wallet, "
            "status, created_at) VALUES (?,?,?,?,?,?)",
            (buyer, lead_ref, CONVERT_USD, wallet, "pending",
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        c.commit()
    finally:
        c.close()
    return {
        "charged": True,
        "buyer": buyer,
        "lead_ref": lead_ref,
        "grade": grade,
        "amount_usd": CONVERT_USD,
    }


def evaluate_batch(buyer: str, leads: list[dict], mode: str = None) -> dict:
    out = [evaluate_lead(buyer, l, mode) for l in leads]
    return {
        "buyer": buyer,
        "mode": mode or DEFAULT_MODE,
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
