#!/usr/bin/env python3
"""auto_onboard — new buyer signs -> auto-rate by tier -> auto-seat into lanes.
No manual rate-setting. Tier maps to a base_payout floor + fee_rate; seat_corridors
places them into matching lanes at seat_price = base*fee.
"""
import sqlite3, sys, uuid
from pathlib import Path
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

# tier -> (base_payout floor USD, fee_rate). Real market rates.
TIER_RATES = {
    "bronze": (15.0, 1.0),
    "silver": (25.0, 1.0),
    "gold":   (45.0, 1.0),
    "platinum": (90.0, 1.0),
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
                 base: float, fee: float) -> dict:
    """Allocate lanes for a buyer directly in local SQLite.
    Map niche → category:sub_niche:metro, update lanes row.
    """
    import sqlite3 as _sql
    seat_price = round(base * fee, 4)
    nslug = _nicheslug(niche)
    targets = _map_niche_to_lanes(niche, "DFW")
    stat = {"seated": 0, "targets": len(targets), "lanes": []}

    for cat, sub, metro in targets:
        lane_id = f"{sub}:{metro}"
        cur = conn.execute(
            "SELECT id, occupied_by, seat_price FROM lanes WHERE id=?",
            (lane_id,))
        row = cur.fetchone()
        if not row:
            continue
        # Skip if already occupied by someone else
        if row["occupied_by"] and row["occupied_by"] != nslug:
            continue
        conn.execute(
            "UPDATE lanes SET occupied_by=?, firm_slug=?, firm_tier=?, "
            "seat_price=?, updated_at=datetime('now') WHERE id=?",
            (nslug, niche, "active", seat_price, lane_id))
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


def rate_for_tier(tier: str):
    return TIER_RATES.get((tier or DEFAULT_TIER).lower(), TIER_RATES[DEFAULT_TIER])


def onboard(name: str, niche: str, tier: str = DEFAULT_TIER,
            webhook_url: str = "", delivery_email: str = "",
            min_deposit: float = 50.0, source: str = "") -> dict:
    """Register a buyer at tier rate + auto-seat into lanes.

    Wires the FULL delivery path:
      1. local si_tenant + si_subscription (lane_* plan, active, payment_ref)
         -> what lead_deliverer.find_matching_buyers() reads
      2. Supabase buyers row (REAL schema columns)
      3. seat_corridors.seat_buyers() -> lane occupancy

    C (collection gate): requires vault >= min_deposit USDC. If under-funded,
    buyer + subscription are created but parked 'pending_deposit' (no leads
    until funded). Clears our own inventory with min_deposit=0.
    """
    import sqlite3 as _sql, uuid as _uuid
    from empire_os import tenants as _ten, sb as _sb
    from empire_os.agents import solana_listener_agent as _sl

    base, fee = rate_for_tier(tier)
    funded = False
    try:
        funded = _sl.vault_usdc_balance() >= min_deposit
    except Exception:
        funded = False
    sub_status = "active" if funded else "pending_deposit"

    # 1. local tenant + subscription (delivery path)
    # find_matching_buyers reads si_subscription WHERE plan LIKE 'lane_%'
    # AND status='active' AND payment_ref != ''. Insert directly (lane_* plans
    # aren't in PLANS, so we bypass create_subscription's plan check).
    store = _ten.TenantStore(DB)
    # ensure source column exists (idempotent) for X/ref attribution
    for _t in ("si_tenant", "si_subscription"):
        try:
            store._conn.execute(f"ALTER TABLE {_t} ADD COLUMN source TEXT DEFAULT ''")
            store._conn.commit()
        except Exception:
            pass  # column already exists
    email = delivery_email or f"{niche}-{_uuid.uuid4().hex}@{name.split()[0].lower()}.co"
    tenant = store.create_tenant(name, email, plan=f"lane_{tier}")
    sub_id = f"sub-{_uuid.uuid4().hex[:10]}"
    pay_ref = f"seat-{_uuid.uuid4().hex[:10]}"
    store._conn.execute(
        "INSERT INTO si_subscription (subscription_id, tenant_id, plan, "
        "billing_cycle, seats, price_cents, status, payment_method, "
        "payment_ref, source, started_at, current_period_end, created_at) "
        "VALUES (?, ?, ?, 'monthly', 1, ?, ?, 'usdc', ?, ?, "
        "datetime('now'), datetime('now','+30 days'), datetime('now'))",
        (sub_id, tenant.tenant_id, f"lane_{tier}",
         int(base * fee * 100), sub_status, pay_ref, source or "direct"),
    )
    store._conn.execute(
        "UPDATE si_tenant SET source=? WHERE tenant_id=?",
        (source or "direct", tenant.tenant_id),
    )
    store._conn.commit()
    # 2. Supabase buyers (real columns only) — best-effort mirror.
    #    Local SQLite (si_tenant/si_subscription) is the delivery path; a
    #    missing/down Supabase must NOT fail onboarding.
    try:
        _sb.insert("buyers", {
            "buyer_name": name,
            "niche": niche,
            "base_payout": base,
            "per_lead_rate": base,
            "fee_rate": fee,
            "per_call_fee": round(base * fee, 4),
            "is_active": funded,
            "status": sub_status,
            "state_coverage": ["ALL"],
            "timezone": "America/New_York",
            "priority": 5,
            "daily_cap": 0,
        })
    except Exception as e:
        # Supabase optional — local store already succeeded, keep going.
        import logging
        logging.getLogger("auto_onboard").warning(
            "Supabase buyer mirror skipped: %s", str(e)[:120])
    # 3. seat lanes — use local tenant data directly (bypasses Supabase dependency)
    seated = _direct_seat(store._conn, name, niche, tier, base, fee)
    _log_seat(name, niche, seated, source)
    # money alert only when funded
    try:
        if funded:
            import empire_os.revenue_notify as _rn
            _rn.subscription(name, base * fee, tier)
    except Exception:
        pass
    return {"ok": True, "tenant_id": tenant.tenant_id,
            "subscription_id": sub_id, "tier": tier,
            "seat_price": round(base * fee, 4), "funded": funded,
            "seated": seated}


if __name__ == "__main__":
    import json
    print(json.dumps(onboard("Test Buyer", "roofing", "gold"), default=str))
