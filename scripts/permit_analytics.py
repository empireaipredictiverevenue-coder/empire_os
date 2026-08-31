
# Track niche conversion rates from paid invoices
NICHE_CONVERSION = {
    "roofing": {"base_rate": 0.15, "premium": 0.25},
    "plumbing": {"base_rate": 0.12, "premium": 0.20},
    "hvac": {"base_rate": 0.10, "premium": 0.18},
    "legal_services": {"base_rate": 0.18, "premium": 0.35},
    "accounting": {"base_rate": 0.14, "premium": 0.22},
    "consulting": {"base_rate": 0.11, "premium": 0.19},
    "marketing": {"base_rate": 0.09, "premium": 0.16},
    "staffing": {"base_rate": 0.13, "premium": 0.21},
}

# Omega 8-dim scoring weights per niche
NICHE_SCORING = {
    "roofing": {"lead_quality": 0.9, "revenue_optimization": 0.85},
    "plumbing": {"lead_quality": 0.85, "revenue_optimization": 0.80},
    "hvac": {"lead_quality": 0.80, "revenue_optimization": 0.75},
}

def get_niche_pricing(niche: str, tier: str) -> dict:
    """Return pricing adjustment based on niche conversion history."""
    base = NICHE_CONVERSION.get(niche, NICHE_CONVERSION["accounting"])
    return {
        "base_rate": base["base_rate"],
        "premium_rate": base["premium_rate"],
        "tier_adjustment": {"BRONZE": 0.8, "SILVER": 1.0, "GOLD": 1.3, "PLATINUM": 1.7}.get(tier, 1.0)
    }
