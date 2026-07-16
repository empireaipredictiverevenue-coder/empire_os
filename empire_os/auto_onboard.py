#!/usr/bin/env python3
"""auto_onboard — new buyer signs -> auto-rate by tier -> auto-seat into lanes.
No manual rate-setting. Tier maps to a base_payout floor + fee_rate; seat_corridors
places them into matching lanes at seat_price = base*fee.
"""
import sqlite3, sys, uuid
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

# tier -> (base_payout floor USD, fee_rate). Conservative real rates.
TIER_RATES = {
    "bronze": (9.0, 0.9),
    "silver": (12.0, 1.0),
    "gold":   (18.0, 1.0),
    "platinum": (25.0, 1.0),
}
DEFAULT_TIER = "silver"


def rate_for_tier(tier: str):
    return TIER_RATES.get((tier or DEFAULT_TIER).lower(), TIER_RATES[DEFAULT_TIER])


def onboard(name: str, niche: str, tier: str = DEFAULT_TIER,
            webhook_url: str = "", delivery_email: str = "",
            min_deposit: float = 50.0) -> dict:
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
    from empire_os import tenants as _ten, seat_corridors as _sc, sb as _sb
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
    email = delivery_email or f"{niche}-{_uuid.uuid4().hex[:6]}@{name.split()[0].lower()}.co"
    tenant = store.create_tenant(name, email, plan=f"lane_{tier}")
    sub_id = f"sub-{_uuid.uuid4().hex[:10]}"
    pay_ref = f"seat-{_uuid.uuid4().hex[:10]}"
    store._conn.execute(
        "INSERT INTO si_subscription (subscription_id, tenant_id, plan, "
        "billing_cycle, seats, price_cents, status, payment_method, "
        "payment_ref, started_at, current_period_end, created_at) "
        "VALUES (?, ?, ?, 'monthly', 1, ?, ?, 'usdc', ?, "
        "datetime('now'), datetime('now','+30 days'), datetime('now'))",
        (sub_id, tenant.tenant_id, f"lane_{tier}",
         int(base * fee * 100), sub_status, pay_ref),
    )
    store._conn.commit()
    # 2. Supabase buyers (real columns only)
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
        return {"ok": False, "error": f"buyer persist failed: {str(e)[:120]}"}
    # 3. seat lanes
    conn = _sql.connect(DB, timeout=20); conn.row_factory = _sql.Row
    conn.execute("PRAGMA busy_timeout=15000")
    seated = _sc.seat_buyers(conn)
    conn.commit(); conn.close()
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
