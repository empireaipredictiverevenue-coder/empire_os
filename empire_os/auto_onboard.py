#!/usr/bin/env python3
"""auto_onboard — new buyer signs -> auto-rate by tier -> auto-seat into lanes.
No manual rate-setting. Tier maps to a base_payout floor + fee_rate; seat_corridors
places them into matching lanes at seat_price = base*fee.
"""
import sqlite3, sys, uuid, os
from pathlib import Path
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

# tier -> (base_payout floor USD, fee_rate). Real market rates.
# Hybrid pricing: monthly seat fee (billed upfront on apply) + per-lead on delivery.
# Values are in CENTS. per_lead is stored on the subscription for the PPL router.
TIER_RATES = {
    "bronze":   {"monthly": 29900, "per_lead": 2500},
    "silver":   {"monthly": 59900, "per_lead": 4900},
    "gold":     {"monthly": 119900, "per_lead": 9900},
    "platinum": {"monthly": 239900, "per_lead": 19900},
}
DEFAULT_TIER = "silver"

# ── Direct lane seating (local DB, no Supabase dependency) ────────────
_SUBS = {}  # populated on first call


def _ensure_subs():
    if _SUBS:
        return
    from empire_os.lanes import CATEGORIES as _C
    _SUBS.update({cat: list(d["subs"].keys()) for cat, d in _C.items()})


def _nicheslug(niche: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (niche or "buyer").lower()).strip("_")


def _map_niche_to_lanes(niche: str, metro: str) -> list[tuple[str, str, str]]:
    """Return (category, sub_niche, metro) tuples for a niche + metro.
    Mirrors seat_corridors.map_buyer_to_lanes but takes raw strings.
    """
    _ensure_subs()
    n = (niche or "").lower().strip()
    m = (metro or "DFW").upper().strip()
    from empire_os.lanes import METROS as _METROS
    if m not in _METROS:
        m = "DFW"
    bm = ["DFW", "NYC"]

    if "mass tort" in n or "legal" in n or "class action" in n:
        return [("mass_torts", s, m2) for s in _SUBS["mass_torts"] for m2 in bm]
    if "roof" in n:
        return [("home_services", s, m) for s in ("residential_roofing", "commercial_roofing")]
    if "insurance" in n:
        return [("financial", "insurance", m)]
    if any(k in n for k in ("debt", "mortgage", "loan", "financial", "cpa")):
        return [("financial", s, m2) for s in _SUBS["financial"] for m2 in bm]
    if any(k in n for k in ("medical", "addiction", "dental", "health")):
        return [("medical_health", s, m2) for s in _SUBS["medical_health"] for m2 in bm]
    if any(k in n for k in ("plumb", "hvac", "electric")):
        return [("home_services", s, m2) for s in _SUBS["home_services"] for m2 in bm]
    return []  # no lane mapping


def _direct_seat(conn, name: str, niche: str, tier: str,
                 base: float, fee: float, tenant_id: str = "") -> dict:
    """Allocate lanes for a buyer directly in local SQLite.

    Seats the buyer into EVERY lane whose sub_niche matches their vertical,
    across all metros that exist in the lanes table (not a hardcoded DFW).
    Skips lanes already occupied by a different buyer.
    """
    seat_price = round(base * fee, 4)
    nslug = _nicheslug(niche)
    n = (niche or "").lower().strip()

    # Derive sub_niches from ACTUAL lane prefixes (not a hardcoded map that
    # can drift from the real lanes table). Match the buyer niche against the
    # set of sub_niche prefixes that exist, so seating always targets real lanes.
    prefixes = [r[0] for r in conn.execute(
        "SELECT DISTINCT substr(id,1,instr(id,':')-1) FROM lanes").fetchall()]
    n_slug = n.replace(" ", "_")
    subs = set()
    # 1) exact prefix match (e.g. niche "hvac" -> prefix "hvac")
    if n_slug in prefixes:
        subs.add(n_slug)
    # 2) substring containment both ways (e.g. "roof" -> residential_roofing,
    #    commercial_roofing, roof_repair; "debt" -> debt_relief; "tort"/"legal"
    #    -> camp_lejeune, paraquat, roundup, zantac, afff, legal_services)
    for pre in prefixes:
        if n_slug in pre or pre in n_slug:
            subs.add(pre)
    if not subs:
        subs.add(nslug)

    stat = {"seated": 0, "targets": 0, "lanes": []}
    for sub in subs:
        for row in conn.execute(
            "SELECT id, occupied_by FROM lanes WHERE id LIKE ?",
            (f"{sub}:%",)):
            stat["targets"] += 1
            lane_id = row["id"]
            if row["occupied_by"] and row["occupied_by"] != (tenant_id or nslug):
                continue
            # Store the REAL tenant_id in occupied_by so the PPL router can
            # resolve the buyer + their per_lead_cents. firm_slug keeps the
            # human-readable niche for display.
            conn.execute(
                "UPDATE lanes SET occupied_by=?, firm_slug=?, firm_tier=?, "
                "seat_price=?, updated_at=datetime('now') WHERE id=?",
                (tenant_id or nslug, niche, "active", seat_price, lane_id))
            stat["seated"] += 1
            stat["lanes"].append(lane_id)
    conn.commit()
    return stat


def _log_seat(name, niche, seated, source):
    """Write seat assignment to feedback log."""
    import json, os
    from datetime import datetime, timezone
    log_dir = Path("/root/empire_os/feedback")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "seat_corridors.jsonl"
        with log_file.open("a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": "seat",
                "buyer_name": name,
                "buyer_niche": niche,
                "source": source or "direct",
                "seated_lanes": seated.get("lanes", []),
                "seated_count": seated.get("seated", 0),
            }) + "\n")
    except Exception as _log_err:
        # non-fatal: logging must not break onboarding
        print(f"[auto_onboard] seat log skipped: {_log_err}")


def rate_for_tier(tier: str) -> dict:
    return TIER_RATES.get((tier or DEFAULT_TIER).lower(), TIER_RATES[DEFAULT_TIER])


def ensure_schema(conn):
    """One-time idempotent column additions. Call at import, NOT per-request."""
    for t in ("si_tenant", "si_subscription"):
        for col, ctype in (("source", "TEXT"), ("webhook_url", "TEXT"), ("niche", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE {t} ADD COLUMN {col} {ctype} DEFAULT ''")
                conn.commit()
            except Exception:
                pass  # already exists
    # per-lead rate lives on the subscription so the PPL router can invoice it
    try:
        conn.execute("ALTER TABLE si_subscription ADD COLUMN per_lead_cents INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass


def onboard(name: str, niche: str, tier: str = DEFAULT_TIER,
            webhook_url: str = "", delivery_email: str = "",
            min_deposit: float = 50.0, source: str = "") -> dict:
    """Clean buyer signup -> rate -> seat -> immediate Solana Pay invoice.

    Single connection from the lock-safe WAL pool. No ALTER in the request
    path (schema ensured at import). Supabase is best-effort and never blocks
    the hot path. Returns a pay link so the buyer can fund immediately.

    Flow:
      tenant + subscription (status=awaiting_payment)
        -> crypto_payment_request() builds Solana Pay URL
        -> subscription.payment_ref = memo, status stays awaiting_payment
      solana_listener confirms the memo on-chain -> activates subscription.
    """
    import uuid as _uuid
    from empire_os import db_handler as _db
    from empire_os import tenants as _ten, sb as _sb

    tier = (tier or DEFAULT_TIER).lower()
    if tier not in TIER_RATES:
        tier = DEFAULT_TIER
    rate = rate_for_tier(tier)            # {monthly: cents, per_lead: cents}
    monthly_cents = rate["monthly"]
    per_lead_cents = rate["per_lead"]
    seat_price = round(monthly_cents / 100, 2)   # monthly seat billed upfront
    per_lead_usdc = round(per_lead_cents / 100, 2)
    amount_cents = monthly_cents                 # Solana Pay link = monthly seat
    MERCHANT_WALLET = os.environ.get("SOLANA_VAULT_WALLET", "")

    conn = _db.get_conn()           # shared WAL pool, 30s busy_timeout
    ensure_schema(conn)

    email = delivery_email or f"{niche}-{_uuid.uuid4().hex}@{name.split()[0].lower()}.co"
    store = _ten.TenantStore()
    # Graceful re-apply: if the email already has a tenant, reuse it and
    # re-issue a fresh pay link. Tenant dataclass now carries source/webhook_url/
    # niche, so get_tenant_by_email constructs cleanly.
    existing = store.get_tenant_by_email(email) if email else None
    if existing:
        tenant = existing
        reused = True
    else:
        tenant = store.create_tenant(name, email, plan=f"lane_{tier}")
        reused = False
    sub_id = None
    if reused:
        # Re-apply: refresh the buyer's existing active subscription with the
        # current hybrid rates (monthly seat + per-lead) instead of stacking
        # duplicate rows. Re-issue a fresh pay link for the seat.
        row = conn.execute(
            "SELECT subscription_id FROM si_subscription WHERE tenant_id=? "
            "AND status IN ('active','awaiting_payment') ORDER BY created_at DESC LIMIT 1",
            (tenant.tenant_id,)).fetchone()
        sub_id = row[0] if row else None
        conn.execute(
            "UPDATE si_subscription SET plan=?, seats=1, price_cents=?, "
            "per_lead_cents=?, status='awaiting_payment', payment_ref='', "
            "webhook_url=?, niche=?, started_at=datetime('now'), "
            "current_period_end=datetime('now','+30 days') "
            "WHERE tenant_id=? AND status IN ('active','awaiting_payment') "
            "ORDER BY created_at DESC LIMIT 1",
            (f"lane_{tier}", amount_cents, per_lead_cents,
             webhook_url or "", niche or "", tenant.tenant_id))
    else:
        sub_id = f"sub-{_uuid.uuid4().hex[:10]}"
        conn.execute(
            "INSERT INTO si_subscription (subscription_id, tenant_id, plan, "
            "billing_cycle, seats, price_cents, per_lead_cents, status, payment_method, "
            "payment_ref, source, webhook_url, niche, started_at, current_period_end, created_at) "
            "VALUES (?, ?, ?, 'monthly', 1, ?, ?, 'awaiting_payment', 'usdc', '', ?, ?, ?, "
            "datetime('now'), datetime('now','+30 days'), datetime('now'))",
            (sub_id, tenant.tenant_id, f"lane_{tier}",
             amount_cents, per_lead_cents, source or "direct",
             webhook_url or "", niche or ""),
        )
    conn.execute(
        "UPDATE si_tenant SET source=?, webhook_url=?, niche=?, name=? WHERE tenant_id=?",
        (source or "direct", webhook_url or "", niche or "", name, tenant.tenant_id))
    conn.commit()

    # Best-effort Supabase mirror (never blocks onboarding)
    try:
        _sb.insert("buyers", {
            "buyer_name": name, "niche": niche,
            "base_payout": seat_price, "per_lead_rate": per_lead_usdc,
            "fee_rate": 1.0, "per_call_fee": per_lead_usdc, "is_active": False,
            "status": "awaiting_payment", "state_coverage": ["ALL"],
            "timezone": "America/New_York", "priority": 5, "daily_cap": 0,
        })
    except Exception:
        pass

    # Seat into lanes (local, no Supabase dependency)
    seated = _direct_seat(conn, name, niche, tier, seat_price, per_lead_usdc,
                          tenant_id=tenant.tenant_id)
    _log_seat(name, niche, seated, source)

    # Immediate Solana Pay invoice so the buyer can fund now
    payment = {}
    try:
        from empire_os.billing import crypto_payment_request, CryptoConfig
        cfg = CryptoConfig(
            vault_wallet=MERCHANT_WALLET,
            usdc_mint=os.environ.get("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
            network="solana")
        req = crypto_payment_request(cfg, amount_cents, tenant.tenant_id, f"lane_{tier}")
        memo = req["memo"]
        conn.execute(
            "UPDATE si_subscription SET payment_ref=?, status='awaiting_payment' "
            "WHERE subscription_id=?", (memo, sub_id))
        conn.commit()
        payment = {
            "asset": "USDC", "network": "Solana",
            "vault_wallet": MERCHANT_WALLET,
            "amount_usdc": seat_price,
            "memo": memo,
            "pay_url": req["qr_data"],
            "note": "Send USDC to this address with the memo to activate your seat.",
        }
    except Exception as _e:
        payment = {"error": str(_e)[:120], "vault_wallet": MERCHANT_WALLET}

    return {"ok": True, "tenant_id": tenant.tenant_id,
            "subscription_id": sub_id, "tier": tier,
            "seat_price": seat_price, "per_lead_usdc": per_lead_usdc,
            "funded": False, "reused": reused,
            "pay_to_wallet": MERCHANT_WALLET,
            "amount_usdc_due": seat_price,
            "seated": seated, "payment": payment}


if __name__ == "__main__":
    import json
    print(json.dumps(onboard("Test Buyer", "roofing", "gold"), default=str))
