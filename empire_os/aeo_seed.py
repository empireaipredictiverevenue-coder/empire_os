#!/usr/bin/env python3
"""aeo_seed — Generate AEO pages for high-supply niches.

Creates index.html in /srv/aeo/{niche}/ that matches the existing
template style (cybersecurity, electrical, etc) with proper CTA,
schema.org markup, and per-niche pricing.

Reads niche_pricing table from amount_policy to set per-lead price.
"""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
AEO_DIR = Path("/srv/aeo")

NICHES = {
    "hvac": {
        "title": "HVAC",
        "schema_type": "HVACBusiness",
        "keywords": "hvac, heating, air conditioning, furnace, heat pump, ductwork, ac repair",
        "body": "AI automation helps HVAC contractors close more emergency calls by responding to leads in seconds, qualifying them by system type and urgency, and booking jobs straight to your calendar 24/7, even while you're on a service call. Right now, you can capture every lead from your marketing spend without paying a dispatcher.",
    },
    "roofing": {
        "title": "Roofing",
        "schema_type": "RoofingContractor",
        "keywords": "roofing, roof repair, shingle, tile, metal roof, storm damage, residential roofing",
        "body": "AI automation helps roofing contractors close more storm-damage and repair jobs by responding to leads in seconds, qualifying them by damage type and insurance status, and booking inspections straight to your calendar 24/7, even after the hail stops. Right now, you can capture every lead from your storm-season marketing spend without a full-time SDR.",
    },
    "solar": {
        "title": "Solar",
        "schema_type": "SolarContractor",
        "keywords": "solar, solar panel, solar installation, residential solar, commercial solar, battery storage",
        "body": "AI automation helps solar installers close more qualified leads by responding instantly, qualifying by roof type and electricity bill, and booking site assessments straight to your calendar 24/7. Right now, you can capture every lead from your digital marketing spend without losing them to competitors who respond first.",
    },
    "real_estate": {
        "title": "Real Estate",
        "schema_type": "RealEstateAgent",
        "keywords": "real estate, realtor, buyer agent, listing agent, property, residential real estate",
        "body": "AI automation helps real estate agents convert more online leads into showings by responding in seconds, qualifying by budget and timeline, and booking tours straight to your calendar 24/7. Right now, you can capture every Zillow and Facebook lead without paying a virtual assistant to follow up.",
    },
    # Vector 2 expansion (2026-07-28) — niches with real lane_leads supply
    "legal_services": {
        "title": "Legal Services",
        "schema_type": "LegalService",
        "keywords": "lawyer, attorney, legal services, personal injury, family law, estate planning",
        "body": "AI automation helps law firms convert more intake calls into signed retainers by responding 24/7, qualifying by case type and jurisdiction, and booking consultations straight to your calendar. Right now, you can capture every web lead without missing after-hours opportunities.",
    },
    "insurance": {
        "title": "Insurance",
        "schema_type": "InsuranceAgency",
        "keywords": "insurance agent, auto insurance, home insurance, life insurance, commercial insurance",
        "body": "AI automation helps insurance agents quote more binds by responding in seconds, qualifying by coverage type and risk profile, and booking policy reviews. Right now, you can capture every comparison-shopper without losing them to the carrier that responds first.",
    },
    "debt_relief": {
        "title": "Debt Relief",
        "schema_type": "FinancialService",
        "keywords": "debt relief, debt consolidation, credit counseling, bankruptcy, debt settlement",
        "body": "AI automation helps debt relief firms convert more distressed callers into enrolled clients by responding instantly, qualifying by debt amount and state, and booking consultations. Right now, you can capture every inbound lead without losing them to a faster competitor.",
    },
    "accounting": {
        "title": "Accounting",
        "schema_type": "AccountingService",
        "keywords": "accountant, CPA, bookkeeping, tax preparation, payroll, financial services",
        "body": "AI automation helps CPAs and accountants win more tax-season clients by responding in seconds during peak demand, qualifying by entity type and complexity, and booking consultations. Right now, you can capture every lead without burning out your front desk during tax season.",
    },
    "mortgage": {
        "title": "Mortgage",
        "schema_type": "MortgageBroker",
        "keywords": "mortgage broker, home loan, refinance, FHA loan, VA loan, mortgage rate",
        "body": "AI automation helps mortgage brokers close more loans by responding in seconds during rate-driven shopping, qualifying by credit and down payment, and booking application appointments. Right now, you can capture every rate-comparison shopper without losing them to Rocket or SoFi.",
    },
    "managed_it": {
        "title": "Managed IT",
        "schema_type": "ITService",
        "keywords": "managed IT, IT support, network security, cloud services, IT consulting, MSP",
        "body": "AI automation helps MSPs convert more inbound leads into signed managed-services contracts by responding in seconds, qualifying by environment and headcount, and booking discovery calls. Right now, you can capture every lead without losing them to a faster-responding competitor.",
    },
    "mold_remediation": {
        "title": "Mold Remediation",
        "schema_type": "HomeAndConstructionBusiness",
        "keywords": "mold removal, mold remediation, black mold, mold inspection, water damage",
        "body": "AI automation helps mold remediation companies respond to urgent calls in seconds, qualify by affected area and severity, and book inspections 24/7. Right now, you can capture every high-intent lead without missing emergency opportunities.",
    },
    "water_damage": {
        "title": "Water Damage Restoration",
        "schema_type": "HomeAndConstructionBusiness",
        "keywords": "water damage, flood restoration, water cleanup, mold, emergency restoration",
        "body": "AI automation helps water damage restoration companies respond to emergencies in seconds, qualify by severity and insurance status, and book same-day inspections. Right now, you can capture every emergency lead without missing time-critical jobs.",
    },
    "fire_damage": {
        "title": "Fire Damage Restoration",
        "schema_type": "HomeAndConstructionBusiness",
        "keywords": "fire damage, smoke damage, fire restoration, soot cleanup, emergency restoration",
        "body": "AI automation helps fire damage restoration companies respond to emergencies in seconds, qualify by insurance and severity, and book immediate inspections. Right now, you can capture every emergency lead without losing them to the first responder on scene.",
    },
    "storm_damage": {
        "title": "Storm Damage Repair",
        "schema_type": "HomeAndConstructionBusiness",
        "keywords": "storm damage, hail damage, wind damage, roof storm, insurance claim",
        "body": "AI automation helps storm damage contractors respond to post-storm leads in seconds, qualify by damage type and insurance, and book emergency inspections. Right now, you can capture every storm-driven lead before they sign with a competitor.",
    },
    "commercial_roofing": {
        "title": "Commercial Roofing",
        "schema_type": "RoofingContractor",
        "keywords": "commercial roofing, flat roof, TPO, EPDM, commercial roof repair",
        "body": "AI automation helps commercial roofing contractors win more bids by responding to RFQs in seconds, qualifying by square footage and scope, and booking site surveys. Right now, you can capture every commercial lead without losing them to the GC's preferred vendor list.",
    },
    "roof_repair": {
        "title": "Roof Repair",
        "schema_type": "RoofingContractor",
        "keywords": "roof repair, leak repair, shingle repair, emergency roofer, roof patch",
        "body": "AI automation helps roof repair specialists respond to leak calls in seconds, qualify by damage scope, and book same-day inspections. Right now, you can capture every emergency repair lead before they patch it themselves.",
    },
    "general_contractor": {
        "title": "General Contractor",
        "schema_type": "GeneralContractor",
        "keywords": "general contractor, home remodel, renovation, construction, home improvement",
        "body": "AI automation helps general contractors respond to bid requests in seconds, qualify by project scope and budget, and book consultations. Right now, you can capture every project lead before they hire the next contractor on Angi.",
    },
    "marketing": {
        "title": "Marketing Agency",
        "schema_type": "ProfessionalService",
        "keywords": "marketing agency, digital marketing, SEO agency, paid ads, social media marketing",
        "body": "AI automation helps marketing agencies respond to RFPs in seconds, qualify by industry and budget, and book discovery calls. Right now, you can capture every inbound lead without losing them to a faster competitor.",
    },
    "real_estate_attorney": {
        "title": "Real Estate Attorney",
        "schema_type": "LegalService",
        "keywords": "real estate attorney, real estate lawyer, closing attorney, title attorney",
        "body": "AI automation helps real estate attorneys respond to closing and contract questions in seconds, qualify by transaction type, and book consultations. Right now, you can capture every referral without missing time-sensitive closings.",
    },
    "tax_resolution": {
        "title": "Tax Resolution",
        "schema_type": "FinancialService",
        "keywords": "tax resolution, IRS problems, tax debt, back taxes, tax attorney, enrolled agent",
        "body": "AI automation helps tax resolution firms convert more distressed callers into clients by responding instantly, qualifying by tax debt amount, and booking consultations. Right now, you can capture every IRS-problem lead without missing the 30-day response window.",
    },
}


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def get_price(c: sqlite3.Connection, niche: str) -> float:
    row = c.execute(
        "SELECT base_price_usdc, multiplier FROM niche_pricing WHERE niche=?",
        (niche,),
    ).fetchone()
    if row:
        return round(row["base_price_usdc"] * row["multiplier"], 2)
    return 12.0


def render(niche: str, cfg: dict, price: float) -> str:
    """Render full AEO HTML matching existing template."""
    vault = os.getenv("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
    pay_url = (
        f"bsc:0x1339b487046B0ad924a10c20b1791608EA8595a8"
        f"?amount={price:.2f}"
        f"&label=Empire%20OS%20{niche.title()}"
        f"&memo=aeo:{niche}"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{cfg['title']} — AEO Authority Page</title>
<meta name="description" content="{cfg['body'][:160]}">
<meta name="keywords" content="{cfg['keywords']}">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
  h1, h2, h2 {{ color: #0a3d62; }}
  .meta {{ color: #666; font-size: 0.9rem; border-bottom: 1px solid #ddd; padding-bottom: 1rem; }}
  blockquote {{ border-left: 3px solid #0a3d62; margin: 1rem 0; padding-left: 1rem; color: #555; }}
  .cta {{ background: #f0f7ff; border: 1px solid #0a3d62; border-radius: 8px; padding: 1.5rem; text-align: center; margin: 2rem 0; }}
  a.btn {{ display: inline-block; background: #0a3d62; color: #fff; padding: .75rem 1.5rem; border-radius: 4px; text-decoration: none; font-weight: 600; }}
</style>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "{cfg['schema_type']}",
  "name": "{cfg['title']} Services",
  "description": "{cfg['body'][:200]}",
  "url": "https://empire-ai.co.uk/aeo/{niche}",
  "offers": {{
    "@type": "Offer",
    "price": "{price:.2f}",
    "priceCurrency": "USDT",
    "availability": "https://schema.org/InStock"
  }}
}}
</script>
</head>
<body>
<h1>{cfg['title']} — Complete Guide & Trusted Resources</h1>
<div class="meta">Published 2026-07-27 · Niche: {niche} · Price: ${price:.2f} USDT/lead</div>

<blockquote>{cfg['body']}</blockquote>

<h2>Why {cfg['title']} contractors choose Empire OS</h2>
<ul>
<li>Pay only for leads delivered, no monthly retainer</li>
<li>Each lead includes verified name, phone, address, niche</li>
<li>Settled in USDT on BSC — no chargebacks</li>
<li>Delivered in seconds to your CRM or webhook</li>
</ul>

<div class="cta">
  <h3>Buy {cfg['title']} Leads Delivered in USDT</h3>
  <p>Pay per lead. Delivered to your CRM. Settled on BSC.</p>
  <p><strong>${price:.2f} USDT / lead</strong></p>
  <a href="{pay_url}" class="btn">Buy Leads Now →</a>
  <p style="margin-top:1rem;font-size:.85rem"><a href="/v1/a2a/quote?product=lead_lane&niche={niche}">Request a custom quote</a></p>
</div>

<h2>How it works</h2>
<ol>
<li>Browse the leads above; pick the {cfg['title']} market you want.</li>
<li>Pay {price:.2f} USDT per lead via the link.</li>
<li>Empire OS delivers verified {niche} leads to your CRM in seconds.</li>
<li>First lead delivered to your inbox within 60 seconds of payment.</li>
</ol>

<img src="/v1/aeo/track?event=impression&niche={niche}" width="1" height="1" alt="" style="position:absolute">
</body>
</html>
"""


def main():
    c = db()
    created = []
    for niche, cfg in NICHES.items():
        target = AEO_DIR / niche / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        price = get_price(c, niche)
        target.write_text(render(niche, cfg, price))
        created.append(niche)
    c.close()
    print(json.dumps({"created": created, "dir": str(AEO_DIR)}, indent=2))


if __name__ == "__main__":
    main()