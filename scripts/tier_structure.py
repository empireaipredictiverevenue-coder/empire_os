#!/usr/bin/env python3
"""
Empire OS Revenue Tier Structure — 3 Tiers + Whale Tier + USDT

Three-tier pricing with an elite Whale tier, all referencing USDT
settlement (not USDC). Built on Empire OS v3 confirmed capabilities.
"""

TIERS = {
    "bronze": {
        "name": "Bronze Tier",
        "price": 299,
        "period": "mo",
        "description": "Entry-level lead qualification + AI scoring",
        "features": [
            "Basic AI lead scoring (0-100)",
            "10 leads/day",
            "Email nurture sequence",
            "Bronze buyer marketplace access",
        ],
        "ideal_for": "SMBs testing lead generation",
        "usdt_settlement": 299,
    },
    "silver": {
        "name": "Silver Tier",
        "price": 599,
        "period": "mo",
        "description": "Full lead qualification + AI scoring + automated seller outreach",
        "features": [
            "Advanced AI lead scoring (0-100)",
            "25 leads/day",
            "Full email nurture",
            "Silver buyer marketplace access",
            "Priority support",
        ],
        "ideal_for": "Growing businesses needing qualified leads",
        "usdt_settlement": 599,
    },
    "gold": {
        "name": "Gold Tier",
        "price": 1199,
        "period": "mo",
        "description": "Enterprise lead qualification + AI scoring + automated seller outreach",
        "features": [
            "Premium AI lead scoring (0-100)",
            "50 leads/day",
            "Dedicated account manager",
            "Gold buyer marketplace access",
            "Gold tier close rate: 75-100%",
            "Email + SMS nurture",
            "AI segmentation",
        ],
        "ideal_for": "Established businesses scaling lead flow",
        "usdt_settlement": 1199,
    },
    "whale": {
        "name": "Whale Tier",
        "price": 4999,
        "period": "mo",
        "description": "Complete self-driving empire operations (30,192 leads)",
        "features": [
            "Premium AI lead scoring (0-100)",
            "Unlimited leads/day",
            "Full empire operations suite",
            "Whale buyer marketplace access",
            "Multi-chain settlements (BSC USDT + Solana USDC)",
            "Dedicated success manager",
            "Custom AI model tuning",
            "Enterprise API access",
        ],
        "ideal_for": "Large enterprises & Fortune 500 autonomous operations",
        "usdt_settlement": 4999,
        "enterprise_pilot": True,
    },
}

# Empire pilot campaigns active
ACTIVE_PILOTS = {
    "emma_coffee_shop": {
        "tier": "silver",
        "account_id": "#15584",
        "monthly_value": 599,
        "status": "live",
        "features": "Silver tier + buyer_marketplace targeting",
    },
    "construction_industry": {
        "tier": "gold",
        "phase": "phase_2_first_conversion",
        "industry": "construction",
        "avg_deal": "$5,000-50,000",
        "status": "active",
        "conversion_flow": "Lead → AI segmentation → Email nurture → Buyer push → USDC settlement",
    },
}

TIER_ORDER = ["bronze", "silver", "gold", "whale"]


def generate_tier_structure():
    """Generate the tier structure section."""
    lines = []
    lines.append("=" * 60)
    lines.append("EMPIRE OS REVENUE TIERS (4-Level)")
    lines.append("=" * 60)
    
    for tier_key in TIER_ORDER:
        tier = TIERS[tier_key]
        lines.append(f"\n{tier['name']} - ${tier['price']}{tier['period']}")
        lines.append(f"  Description: {tier['description']}")
        lines.append(f"  Features: {', '.join(tier['features'])}")
        lines.append(f"  Ideal for: {tier['ideal_for']}")
        lines.append(f"  USDT settlement: ${tier['usdt_settlement']}")
    
    # Add active pilots
    lines.append(f"\nACTIVE ENTERPILOTS:")
    for key, pilot in ACTIVE_PILOTS.items():
        lines.append(f"  {key}: {pilot}")
    
    return "\n".join(lines)


def generate_whale_tier():
    """Generate the whale tier detail."""
    whale = TIERS["whale"]
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("WHALE TIER (Elite - Enterprise)")
    lines.append("=" * 60)
    lines.append(f"\n{whale['name']} - ${whale['price']}{whale['period']}")
    lines.append(f"  Description: {whale['description']}")
    lines.append(f"  Features: {', '.join(whale['features'])}")
    lines.append(f"  Ideal for: {whale['ideal_for']}")
    lines.append(f"  USDT settlement: ${whale['usdt_settlement']}")
    lines.append(f"  Enterprise pilot active: {whale['enterprise_pilot']}")
    
    for pilot_key, pilot in ACTIVE_PILOTS.items():
        lines.append(f"  Pilot: {pilot_key} — {pilot}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_tier_structure())
    print(generate_whale_tier())