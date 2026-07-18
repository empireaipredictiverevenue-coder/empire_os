#!/usr/bin/env python3
"""Generate the buy-side landing page (lead buyer recruitment) + publish to AEO surface."""
import sys, subprocess
sys.path.insert(0, "/root/empire_os")
import product_spec as ps

BUY_SPEC = {
    "sku": "buy_leads",
    "name": "Buy Verified B2B Leads",
    "tagline": "Exclusive leads per lane — settle in USDC",
    "description": "Claim a seat in a vertical lane (logistics, roofing, HVAC, AI services). "
                   "Get verified, exclusive B2B leads — real company domains, one buyer per lane. "
                   "No per-lead junk fees. Tiers: bronze $15 / silver $25 / gold $45 / platinum $90 equivalent.",
    "tech": "Lane/seat-corridor model. CRM 29k+ real leads. USDC settlement (TS-5), no Stripe, no KYC. "
            "MCP supply layer for agents.",
    "specs": [("Model", "One buyer per lane (exclusive)"),
              ("Lead source", "29k+ verified B2B businesses"),
              ("Settlement", "USDC, no KYC"),
              ("Access", "MCP tool + this page")],
    "tiers": {"T1": 199, "T2": 599, "T3": 1999, "T4": 5999},
    "cta_url": "/buy-leads", "settled": "USDC (TS-5)",
}

if __name__ == "__main__":
    p = ps.publish(BUY_SPEC, surface_root="/tmp/aeo_buy")
    subprocess.run(["incus", "exec", "empire-hub", "--", "sh", "-c", "mkdir -p /srv/aeo/buy_leads"],
                   capture_output=True, timeout=20)
    subprocess.run(["incus", "file", "push", "--recursive", "/tmp/aeo_buy/products/buy_leads",
                    "empire-hub", "/srv/aeo/buy_leads/"], capture_output=True, timeout=30)
    subprocess.run(["rm", "-rf", "/tmp/aeo_buy"])
    print("buy-side landing published -> /aeo/buy_leads/")
