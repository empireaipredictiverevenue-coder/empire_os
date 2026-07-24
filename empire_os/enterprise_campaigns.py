#!/usr/bin/env python3
"""Empire OS — Enterprise Campaign Family (north-mini blueprint, REAL data).

Builds the campaign family north-mini specced, on REAL DB audiences:
  1. 7-day outbound to received leads  -> subscriber conversion
  2. PPC campaign -> hero SKU (enterprise $999/mo tier, per rates.md)
  3. Weekly lead-gen campaign (recurring)
  4. Lead-gen reactivation (marketplace / PPC)

HYBRID: uses northmini_realstate for truthful counts (no fabricated "4 leads"
or "$100M"). Every audience_size is a live query. No simulated revenue.

Writes to outbound_campaigns. Idempotent: skips if a campaign of same name
already exists (status preserved).

Run: /root/venv/bin/python3 empire_os/enterprise_campaigns.py
"""
import sqlite3, sys, json
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"

from empire_os.northmini_realstate import real_state

# enterprise hero SKU (rates.md: enterprise $999/mo seat tier)
ENTERPRISE_TIER = "enterprise"
ENTERPRISE_SEAT_USD = 999.0


def _audience(real: dict, kind: str) -> int:
    """Real audience size for a campaign kind."""
    if kind == "received_leads":
        return real["lane_leads"]
    if kind == "enterprise_upsell":
        # lane_silver tenants not yet on enterprise tier
        return real["tenants_seated"]
    if kind == "weekly_leadgen":
        return real["buyers"]
    if kind == "reactivation":
        return real["lane_leads"]
    return 0


def build() -> list:
    real = real_state()
    campaigns = [
        {
            "name": "7day-outbound-received-leads",
            "niche": "all",
            "lane": "all",
            "tier": ENTERPRISE_TIER,
            "angle": "Convert received leads to paying subscribers via 12-SKU tiers + QR pay link",
            "audience_kind": "received_leads",
        },
        {
            "name": "ppc-hero-sku-enterprise",
            "niche": "roofing",
            "lane": "commercial_roofing",
            "tier": ENTERPRISE_TIER,
            "angle": f"PPC campaign for enterprise seat (${ENTERPRISE_SEAT_USD:.0f}/mo) — hero SKU from pricing.md",
            "audience_kind": "enterprise_upsell",
        },
        {
            "name": "weekly-leadgen",
            "niche": "all",
            "lane": "all",
            "tier": "silver",
            "angle": "Recurring weekly lead-gen campaign across 42 niches / 11 metros",
            "audience_kind": "weekly_leadgen",
        },
        {
            "name": "leadgen-reactivation",
            "niche": "all",
            "lane": "all",
            "tier": "silver",
            "angle": "Reactivation: marketplace + PPC to stalled pipeline (behavior_engine leak: cold stage)",
            "audience_kind": "reactivation",
        },
    ]

    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    created = []
    for camp in campaigns:
        exists = c.execute(
            "SELECT name FROM outbound_campaigns WHERE name=?",
            (camp["name"],)).fetchone()
        if exists:
            created.append(f"skip(exists):{camp['name']}")
            continue
        aud = _audience(real, camp["audience_kind"])
        c.execute(
            "INSERT INTO outbound_campaigns "
            "(name, niche, lane, tier, angle, status, audience_size, sent, billed, collected, created_at) "
            "VALUES (?,?,?,?,?,'draft',?,0,0,0,?)",
            (camp["name"], camp["niche"], camp["lane"], camp["tier"],
             camp["angle"], aud, datetime.now(timezone.utc).isoformat()))
        created.append(f"created:{camp['name']}(aud={aud})")
    c.commit()
    c.close()
    return created


if __name__ == "__main__":
    print(json.dumps({
        "real_state": real_state(),
        "campaigns": build(),
    }, indent=2))
