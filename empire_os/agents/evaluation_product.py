"""Empire Cortex — Evaluation Product (REAL, not the $121/hr fiction).

Packages the Cortex Judge's lead-evaluation into a billable product:
a buyer posts a lead (or batch), we score it with the real Omega pipeline
(omega_os.qualify_prospect), return a grade, and bill per the HYBRID model.

HYBRID PRICING (best of both worlds):
  - Grading is FREE for every lead (Omega score + A/B/C/D grade).
  - OUTCOME mode (default): charge only when a graded A/B/C lead CONVERTS.
        EVAL_CONVERT_USD = 2.50   # per A/B/C lead that converts  (raised 2026-07-20: $0.50 -> $2.50)
  - PER_SCORE mode (opt-in, casual buyers): charge per lead scored.
        EVAL_PRICE_USD = 0.20     # volume rate
  - MINIMUM DEAL SIZE: a single settlement is only worth it at >= $10.
        EVAL_MIN_USD = 10.00      # floor on any USDC charge / pay link
    Below $10 the deal isn't worth the rail + support cost, so the Solana
    Pay link always demands >= $10 (covers the conversion + future ones,
    or a buyer prepays the $10 floor to activate).
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
CONVERT_USD = float(os.environ.get("EVAL_CONVERT_USD", "2.50"))  # per A/B/C conversion (raised 2026-07-20)
DEFAULT_MODE = os.environ.get("EVAL_MODE", "outcome")           # outcome | per_score
MIN_USD = float(os.environ.get("EVAL_MIN_USD", "10.00"))         # floor: deal < $10 not worth it


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
    # Fee-aware on-chain model: a buyer purchases a CREDIT PACK once on-chain
    # (>= $10 floor). Each conversion debits 1 credit OFF-CHAIN (no tx). The
    # chain only sees the single purchase tx -> blockchain fees amortised.
    c.execute(
        """CREATE TABLE IF NOT EXISTS evaluation_credits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer TEXT UNIQUE,
            credits_remaining INTEGER DEFAULT 0,
            funded_usd REAL DEFAULT 0,
            updated_at TEXT
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


def signup(name: str, niche: str = "", wallet: str = "", email: str = "") -> dict:
    """Self-serve buyer onboarding: create an si_tenant + issue an API key.

    Returns {tenant_id, api_key}. Idempotent-ish: a repeat name gets a fresh key
    only if none active exists. Wallet (USDC) is stored for settlement lookups.
    """
    import secrets, re
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "name required"}
    tenant_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or f"buyer_{int(time.time())}"
    api_key = "evk_" + secrets.token_urlsafe(24)
    c = _db()
    try:
        _ensure_tenant_cols(c)
        # ensure crypto_wallet col exists (used by _buyer_wallet)
        cols = {r[1] for r in c.execute("PRAGMA table_info(si_tenant)").fetchall()}
        if "crypto_wallet" not in cols:
            c.execute("ALTER TABLE si_tenant ADD COLUMN crypto_wallet TEXT")
        existing = c.execute(
            "SELECT tenant_id, api_key FROM si_tenant WHERE tenant_id=? AND status='active'",
            (tenant_id,)).fetchone()
        if existing and existing[1]:
            return {"ok": True, "tenant_id": existing[0], "api_key": existing[1],
                    "note": "existing active tenant"}
        c.execute(
            "INSERT OR REPLACE INTO si_tenant "
            "(tenant_id, name, email, plan, billing_cycle, status, api_key, "
            "crypto_wallet, delivery_email, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id, name, email or f"{tenant_id}@eval.local", "eval",
             "one_off", "active", api_key, wallet, email,
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        c.commit()
    except sqlite3.OperationalError as e:
        return {"ok": False, "error": f"si_tenant unavailable: {e}"}
    finally:
        c.close()
    return {"ok": True, "tenant_id": tenant_id, "api_key": api_key, "niche": niche}


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
        # Fee-aware path: if buyer holds credits, debit 1 off-chain (no tx).
        if credit_balance(buyer) > 0:
            c.execute(
                "UPDATE evaluation_credits SET credits_remaining=credits_remaining-1, "
                "updated_at=? WHERE buyer=?",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), buyer),
            )
            c.execute(
                "UPDATE evaluation_ledger SET price_usd=?, status='billed_credit' WHERE id=?",
                (CONVERT_USD, lid),
            )
            c.execute(
                "INSERT INTO evaluation_conversions (buyer, lead_ref, charged_usd, created_at) "
                "VALUES (?,?,?,?)",
                (buyer, lead_ref, 0.0,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            )
            c.commit()
            return {
                "charged": True,
                "buyer": buyer,
                "lead_ref": lead_ref,
                "grade": grade,
                "amount_usd": 0.0,
                "credited": True,
                "credits_remaining": credit_balance(buyer),
                "pay_memo": "",
                "pay_url": "",
            }
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
    memo = f"EVAL_{buyer}__{lead_ref}"
    vault = os.environ.get("SOLANA_VAULT_WALLET", "").strip()
    pay_url = ""
    demand = max(CONVERT_USD, MIN_USD)   # enforce $10 floor: deal < $10 not worth it
    if vault:
        import urllib.parse
        pay_url = (f"solana:{vault}?amount={demand:.2f}"
                   f"&spl-token=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                   f"&memo={urllib.parse.quote(memo)}&label={urllib.parse.quote(memo)}")
    return {
        "charged": True,
        "buyer": buyer,
        "lead_ref": lead_ref,
        "grade": grade,
        "amount_usd": CONVERT_USD,
        "demand_usd": round(demand, 2),
        "pay_memo": memo,
        "pay_url": pay_url,
    }


def credit_balance(buyer: str) -> int:
    """Remaining fee-aware credits for a buyer (0 if none)."""
    c = _db()
    try:
        row = c.execute(
            "SELECT credits_remaining FROM evaluation_credits WHERE buyer=?",
            (buyer,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        c.close()


def buy_pack(buyer: str, usd: float = None) -> dict:
    """Fee-aware on-chain purchase: ONE Solana Pay tx funds a credit pack.

    Credits = floor(usd / CONVERT_USD) (e.g. $10 -> 20 conversions). The buyer
    pays once on-chain; conversions then draw down credits OFF-CHAIN, so blockchain
    fees are amortised across many leads instead of one tx per $0.50.
    Enforces the $10 minimum deal size.
    """
    usd = float(usd or MIN_USD)
    demand = max(usd, MIN_USD)
    credits = int(demand // CONVERT_USD)
    pack_id = f"pack_{int(time.time())}"
    memo = f"EVALBUY_{buyer}_{pack_id}"
    c = _db()
    try:
        wallet = _buyer_wallet(c, buyer)
        c.execute(
            "INSERT INTO evaluation_settlements (buyer, lead_ref, amount_usd, wallet, "
            "status, created_at) VALUES (?,?,?,?,?,?)",
            (buyer, memo, demand, wallet, "pending_pack",
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        c.commit()
    finally:
        c.close()
    vault = os.environ.get("SOLANA_VAULT_WALLET", "").strip()
    pay_url = ""
    if vault:
        import urllib.parse
        pay_url = (f"solana:{vault}?amount={demand:.2f}"
                   f"&spl-token=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                   f"&memo={urllib.parse.quote(memo)}&label={urllib.parse.quote(memo)}")
    return {
        "buyer": buyer,
        "pack_id": pack_id,
        "credits": credits,
        "charge_usd": round(demand, 2),
        "pay_memo": memo,
        "pay_url": pay_url,
    }


def _settle_pack(memo: str, tx_sig: str) -> bool:
    """Replay hook: a EVALBUY_ memo credits the buyer's balance (one on-chain tx)."""
    if not memo.startswith("EVALBUY_"):
        return False
    rest = memo.replace("EVALBUY_", "", 1).strip()
    buyer, _, pack_id = rest.partition("_")
    c = _db()
    try:
        srow = c.execute(
            "SELECT amount_usd FROM evaluation_settlements "
            "WHERE buyer=? AND lead_ref=? AND status='pending_pack' "
            "ORDER BY id DESC LIMIT 1",
            (buyer, memo),
        ).fetchone()
        if not srow:
            return False
        credits = int(float(srow[0]) // CONVERT_USD)
        c.execute(
            "INSERT INTO evaluation_credits (buyer, credits_remaining, funded_usd, updated_at) "
            "VALUES (?,?,?,?) ON CONFLICT(buyer) DO UPDATE SET "
            "credits_remaining=credits_remaining+?, funded_usd=funded_usd+?, "
            "updated_at=?",
            (buyer, credits, float(srow[0]),
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             credits, float(srow[0]),
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        c.execute(
            "UPDATE evaluation_settlements SET status='settled', tx_sig=? "
            "WHERE buyer=? AND lead_ref=? AND status='pending_pack'",
            (tx_sig, buyer, memo),
        )
        c.commit()
        return True
    finally:
        c.close()


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


def claim_prospect(buyer: str, lead_ref: str) -> dict:
    """Claim a pre-graded prospect (e.g. from reddit_scraper to-ledger push).

    Updates the existing evaluation_ledger row's buyer + status='claimed'
    so record_conversion() will charge CONVERT_USD when the buyer later
    marks it sold. Idempotent: re-claiming the same lead_ref is a no-op.
    """
    if not buyer or not lead_ref:
        return {"ok": False, "error": "buyer + lead_ref required"}
    c = _db()
    try:
        row = c.execute(
            "SELECT id, grade, status, niche FROM evaluation_ledger "
            "WHERE lead_ref=? ORDER BY id DESC LIMIT 1",
            (lead_ref,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": f"lead_ref {lead_ref!r} not found in ledger"}
        lid, grade, status, niche = row
        if status == "billed" or status == "billed_credit":
            return {"ok": False, "error": f"already billed (status={status})",
                    "grade": grade, "niche": niche}
        if status == "claimed" and c.execute(
            "SELECT buyer FROM evaluation_ledger WHERE id=?", (lid,)
        ).fetchone()[0] != buyer:
            return {"ok": False, "error": "already claimed by another buyer",
                    "grade": grade, "niche": niche}
        c.execute(
            "UPDATE evaluation_ledger SET buyer=?, status='claimed' WHERE id=?",
            (buyer, lid),
        )
        c.commit()
        return {
            "ok": True, "ledger_id": lid, "buyer": buyer, "lead_ref": lead_ref,
            "grade": grade, "niche": niche, "status": "claimed",
            "note": "use /v1/evaluate/conversion to mark sold and charge",
        }
    finally:
        c.close()


def score_audit(url: str, persist: bool = True) -> dict:
    """Run free audit lead-magnet on a URL.

    Returns {url, score (0-100), grade (A/B/C/D/F), checks, audit_report_path}.
    If persist=True, writes the audit as an awaiting_buyer row in
    evaluation_ledger so a buyer can claim + later mark it sold (charge $2.50).

    Falls back to a synthetic grade if the audit pipeline is unavailable
    (e.g. in a slim container without claude-seo scripts).
    """
    import hashlib
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "url required"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    result: dict = {"ok": True, "url": url}
    try:
        from empire_os.audit_api import run_audit
        audit = run_audit(url)
        result.update({
            "score": int(audit.get("score", 0)),
            "grade": audit.get("grade", "F"),
            "checks": audit.get("checks", {}),
            "audited_at": audit.get("audited_at"),
        })
    except Exception as e:
        # Fallback: lightweight header check (free, no external deps)
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "EmpireOS/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode("utf-8", "ignore")[:50000]
                status = r.status
            has_title = "<title>" in body.lower()
            has_meta = 'name="description"' in body.lower()
            has_h1 = "<h1" in body.lower()
            has_ssl = url.startswith("https://")
            score = sum([20 if has_ssl else 0, 20 if has_title else 0,
                         20 if has_meta else 0, 20 if has_h1 else 0, 20 if status == 200 else 0])
            grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
            result.update({
                "score": score, "grade": grade,
                "checks": {"https": has_ssl, "title": has_title,
                           "meta_description": has_meta, "h1": has_h1,
                           "status": status},
                "fallback": True,
                "fallback_reason": str(e)[:100],
            })
        except Exception as e2:
            return {"ok": False, "error": f"audit failed: {e2}"}

    if persist:
        url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        lead_ref = f"audit_{url_hash}"
        c = _db()
        try:
            c.execute(
                "INSERT OR IGNORE INTO evaluation_ledger "
                "(buyer, lead_ref, niche, omega, grade, price_usd, billing, status, created_at) "
                "VALUES ('', ?, 'audit', ?, ?, 0.0, 'outcome', 'awaiting_buyer', ?)",
                (lead_ref, round(result["score"] / 100.0, 4),
                 result["grade"], time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            )
            c.commit()
            result["lead_ref"] = lead_ref
            result["billable"] = result["grade"] in ("A", "B", "C")
        finally:
            c.close()
    return result


if __name__ == "__main__":
    # smoke test (no network, real omega scoring on a dummy lead)
    r = evaluate_lead("smoke_test", {"ref": "smoke_1", "details": "roof repair Queens NY", "name": "Joe", "phone": "5551234", "zip_code": "11368"})
    print("SMOKE:", json.dumps(r))
    print("LEDGER TOTAL:", ledger_total())
