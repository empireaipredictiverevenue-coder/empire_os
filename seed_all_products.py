#!/usr/bin/env python3
"""Complete product catalog for Empire OS Revenue Blitz.

Products:
- LeadFlow T1-T4 (marketplace seats)
- v4 Enterprise Intelligence (high-ticket)
- ICO/Capital Raise Track (2 tiers)
"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/empire_os")
DB = ROOT / "empire_os.db"

PRODUCTS = [
    # ─── LeadFlow: Marketplace Seats (per-lead B2B) ───
    {
        "sku": "leadflow_t1",
        "name": "LeadFlow T1 — Starter",
        "tagline": "25 exclusive scored leads/month, ICP-matched, delivered via portal",
        "description": "Entry marketplace seat. 25 exclusive B2B leads per month, scored (Omega ≥15), ICP-matched to your vertical, delivered via private audit portal with revenue leak analysis. Includes waterfall enrichment, CRM sync webhook, and monthly portfolio review.",
        "tech": "Python/Scout enrichment, Omega scoring, AEO portal, webhook delivery",
        "specs": [
            ("Leads/month", "25"),
            ("Exclusivity", "Full — lead sold to 1 buyer"),
            ("Scoring", "Omega 15-40, ICP tier A/B"),
            ("Enrichment", "15-source waterfall (whois, BBB, Hunter, Apollo, etc.)"),
            ("Delivery", "Portal + webhook + email"),
            ("CRM Sync", "Twenty, HubSpot, custom webhook"),
            ("Support", "Email SLA 24h"),
        ],
        "tiers": {"T1": 497},
        "setup_fee_usdc": 0,
        "b2b_angle": "Predictable lead flow for SMB service businesses (HVAC, plumbing, roofing, solar)",
        "cta_url": "/v1/buyers/signup-seat?sku=leadflow_t1",
        "features": json.dumps(["25 leads/mo", "Omega scoring", "ICP matching", "Portal access", "Webhook delivery"]),
        "benefits": json.dumps(["Revenue leak audit per lead", "Exclusive territory", "No contract", "Cancel anytime"]),
        "deliverables": json.dumps(["Monthly lead pack", "Audit portal links", "CRM webhook events", "Portfolio summary"]),
    },
    {
        "sku": "leadflow_t2",
        "name": "LeadFlow T2 — Growth",
        "tagline": "75 leads/mo + waterfall priority + dedicated lane access",
        "description": "Growth seat. 75 exclusive scored leads/month with waterfall priority (first access to new sweep batches), dedicated vertical lane, advanced ICP filters, and weekly portfolio optimization call.",
        "tech": "Python/Scout enrichment, Omega scoring, AEO portal, webhook delivery, lane routing",
        "specs": [
            ("Leads/month", "75"),
            ("Exclusivity", "Full — lead sold to 1 buyer"),
            ("Scoring", "Omega 15-40, ICP tier A/B"),
            ("Enrichment", "15-source waterfall + priority queue"),
            ("Delivery", "Portal + webhook + email + lane router"),
            ("CRM Sync", "Twenty, HubSpot, Salesforce, custom webhook"),
            ("Support", "Email SLA 4h + weekly call"),
            ("Lane Access", "1 dedicated vertical lane"),
        ],
        "tiers": {"T2": 1247},
        "setup_fee_usdc": 0,
        "b2b_angle": "Scale lead flow for growing service companies and regional operators",
        "cta_url": "/v1/buyers/signup-seat?sku=leadflow_t2",
        "features": json.dumps(["75 leads/mo", "Waterfall priority", "Dedicated lane", "Weekly optimization", "Advanced ICP"]),
        "benefits": json.dumps(["First access to sweeps", "Lane exclusivity", "Portfolio optimization", "No contract"]),
        "deliverables": json.dumps(["Monthly lead pack", "Audit portal links", "Lane router events", "Weekly optimization report"]),
    },
    {
        "sku": "leadflow_t3",
        "name": "LeadFlow T3 — Scale",
        "tagline": "200 leads/mo + dedicated lane + CRM sync + custom ICP",
        "description": "Scale seat. 200 exclusive scored leads/month with custom ICP model trained on your closed-won data, multi-lane access, dedicated account manager, and real-time CRM sync.",
        "tech": "Python/Scout enrichment, Omega scoring, AEO portal, webhook delivery, lane routing, custom ML",
        "specs": [
            ("Leads/month", "200"),
            ("Exclusivity", "Full — lead sold to 1 buyer"),
            ("Scoring", "Custom Omega model + ICP tier A/B/C"),
            ("Enrichment", "15-source waterfall + custom signals"),
            ("Delivery", "Portal + webhook + email + lane router + SFTP"),
            ("CRM Sync", "Real-time bi-directional (Twenty, HubSpot, SF, custom)"),
            ("Support", "Dedicated account manager + Slack"),
            ("Lane Access", "Up to 5 vertical lanes"),
            ("Custom ICP", "ML model trained on your wins"),
        ],
        "tiers": {"T3": 2497},
        "setup_fee_usdc": 0,
        "b2b_angle": "Full funnel automation for multi-location operators and national brands",
        "cta_url": "/v1/buyers/signup-seat?sku=leadflow_t3",
        "features": json.dumps(["200 leads/mo", "Custom ICP model", "Multi-lane", "Real-time CRM", "Dedicated manager"]),
        "benefits": json.dumps(["Predictable volume", "Lane portfolio", "ML optimization", "No contract"]),
        "deliverables": json.dumps(["Monthly lead pack", "Audit portal links", "Real-time CRM events", "Monthly strategy review"]),
    },
    {
        "sku": "leadflow_t4",
        "name": "LeadFlow T4 Titanium — Enterprise",
        "tagline": "Unlimited vertical lanes + white-label + API access + revenue share",
        "description": "Enterprise seat. Unlimited leads across all verticals, white-label portal for your brand, full API access for agent-to-agent commerce, revenue share on resold leads, and dedicated infrastructure.",
        "tech": "Python/Scout enrichment, Omega scoring, white-label AEO portal, full API, A2A commerce, custom infra",
        "specs": [
            ("Leads/month", "Unlimited (fair use)"),
            ("Exclusivity", "Configurable — exclusive or shared"),
            ("Scoring", "Custom Omega + your proprietary signals"),
            ("Enrichment", "All sources + private data integrations"),
            ("Delivery", "White-label portal + API + webhook + SFTP + A2A"),
            ("CRM Sync", "Real-time bi-directional + custom objects"),
            ("Support", "Dedicated team + SLA + on-prem option"),
            ("Lane Access", "All 62 vertical lanes"),
            ("White-label", "Full brand + domain + custom portal"),
            ("API Access", "Full A2A commerce + lead API"),
            ("Revenue Share", "20% on resold leads"),
        ],
        "tiers": {"T4": 4997},
        "setup_fee_usdc": 9997,
        "b2b_angle": "White-label lead gen platform for agencies, franchisors, and enterprise buyers",
        "cta_url": "/v1/buyers/signup-seat?sku=leadflow_t4",
        "features": json.dumps(["Unlimited leads", "White-label portal", "Full API/A2A", "Revenue share", "All lanes"]),
        "benefits": json.dumps(["Brand ownership", "Agent commerce", "Reseller margins", "SLA guarantee"]),
        "deliverables": json.dumps(["White-label portal", "API keys + docs", "A2A agent config", "Monthly business review"]),
    },

    # ─── v4 Enterprise Intelligence ───
    {
        "sku": "v4_enterprise_intelligence",
        "name": "v4 Enterprise Intelligence",
        "tagline": "Predictive revenue engine — cortex scores, A2A commerce, AEO dominance",
        "description": "Full-stack intelligence product. Predictive revenue modeling (Cortex Engine), automated AEO page generation (3,854+ pages), agent-to-agent commerce (MCP), real-time corridor monitoring, and executive dashboard. Runs on your infrastructure or ours.",
        "tech": "Cortex Engine (predictive), AEO Generator (3,854 pages), MCP Server (A2A), Cortex AI Assistant, Cortex Health Watchdog",
        "specs": [
            ("Cortex Engine", "Live revenue prediction + 4 pillars (Scout, Auditor, Messenger, Creative)"),
            ("AEO Pages", "3,854+ auto-generated, indexed, cited by LLMs"),
            ("A2A Commerce", "MCP server on :8082 — list_open_lanes, quote_lane, buy_leads"),
            ("Corridor Monitoring", "Real-time seat_corridors + lane_router + ppc_router"),
            ("Executive Dashboard", "Real-time funnel, revenue, settlements, buyer health"),
            ("Deployment", "Your cloud (AWS/GCP/Azure) or Empire OS managed"),
            ("Support", "Dedicated engineer + SLA + on-prem option"),
            ("Integration", "Twenty CRM, Pinecone, PostHog, Listmonk, custom APIs"),
        ],
        "tiers": {"Monthly": 4997},
        "setup_fee_usdc": 9997,
        "b2b_angle": "Enterprise revenue intelligence for PE-backed platforms, franchisors, and national operators",
        "cta_url": "/v1/buyers/enterprise?sku=v4_enterprise_intelligence",
        "features": json.dumps(["Cortex predictive engine", "AEO dominance (3,854 pages)", "A2A commerce (MCP)", "Corridor monitoring", "Executive dashboard"]),
        "benefits": json.dumps(["Revenue prediction", "LLM visibility", "Agent commerce", "Real-time optimization", "Full ownership"]),
        "deliverables": json.dumps(["Cortex engine deploy", "AEO page network", "MCP server + keys", "Dashboard access", "Monthly strategy review"]),
    },

    # ─── ICO / Capital Raise Track ───
    {
        "sku": "ico_capital_raise_entry",
        "name": "ICO/Capital Raise — Entry Pack",
        "tagline": "Accredited investor lead pack + outreach sequences",
        "description": "Capital raise starter. Curated list of accredited investors (family offices, VCs, angels) matched to your sector, with verified contact info, outreach templates, and CRM-ready delivery.",
        "tech": "Investor database, LinkedIn/Signal verification, email waterfall, CRM sync",
        "specs": [
            ("Investor Leads", "50 verified accredited investors"),
            ("Verification", "LinkedIn + Signal + SEC Form D + Crunchbase"),
            ("Contact Info", "Email + LinkedIn + phone (where available)"),
            ("Outreach", "5-sequence templates + personalization variables"),
            ("CRM Sync", "Twenty, HubSpot, Airtable, CSV"),
            ("Compliance", "Reg D 506(c) ready, accredited verification"),
            ("Support", "Email support + template review"),
        ],
        "tiers": {"Entry": 2999},
        "setup_fee_usdc": 0,
        "b2b_angle": "First capital raise for B2B SaaS, marketplace, and service platforms",
        "cta_url": "/v1/buyers/enterprise?sku=ico_capital_raise_entry",
        "features": json.dumps(["50 verified investors", "Outreach sequences", "CRM ready", "Compliance ready"]),
        "benefits": json.dumps(["Targeted capital", "Time savings", "Verified contacts", "Template library"]),
        "deliverables": json.dumps(["Investor CSV/JSON", "Outreach templates", "CRM import guide", "Compliance checklist"]),
    },
    {
        "sku": "ico_capital_raise_scale",
        "name": "ICO/Capital Raise — Full Funnel",
        "tagline": "Full raise funnel: investor sourcing → outreach → data room → close",
        "description": "End-to-end capital raise. 200+ investor sourcing, automated outreach agent (A2A), data room setup, term sheet negotiation support, and close management. Runs on Empire OS A2A commerce layer.",
        "tech": "Investor database, A2A outreach agent, data room (secure), MCP commerce, analytics",
        "specs": [
            ("Investor Leads", "200+ verified accredited investors"),
            ("Verification", "LinkedIn + Signal + SEC Form D + Crunchbase + private networks"),
            ("Outreach Agent", "Automated A2A agent — personalized, tracked, optimized"),
            ("Data Room", "Secure Notion/Drive + access logs + NDA workflow"),
            ("Term Sheet", "Template library + negotiation playbook"),
            ("Close Management", "Signature workflow + wire tracking + cap table"),
            ("Analytics", "Open/click/reply rates + investor heatmap"),
            ("Support", "Dedicated capital advisor + weekly sync"),
        ],
        "tiers": {"Scale": 9999},
        "setup_fee_usdc": 0,
        "b2b_angle": "Series A/B raise for B2B platforms with $1M+ ARR targeting $5M-$50M rounds",
        "cta_url": "/v1/buyers/enterprise?sku=ico_capital_raise_scale",
        "features": json.dumps(["200+ investors", "A2A outreach agent", "Data room", "Term sheet support", "Close management"]),
        "benefits": json.dumps(["Full funnel automation", "Agent outreach", "Negotiation leverage", "Close certainty"]),
        "deliverables": json.dumps(["Investor database", "Outreach agent config", "Data room access", "Close dashboard"]),
    },
]

import json

def seed_products():
    con = sqlite3.connect(str(DB), timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    
    # Ensure table exists with all columns
    con.execute("""
        CREATE TABLE IF NOT EXISTS si_products (
            sku TEXT PRIMARY KEY,
            name TEXT,
            repo_url TEXT DEFAULT '',
            license TEXT DEFAULT '',
            description TEXT DEFAULT '',
            b2b_angle TEXT DEFAULT '',
            tier1_usdc REAL DEFAULT 0,
            tier2_usdc REAL DEFAULT 0,
            tier3_usdc REAL DEFAULT 0,
            tier4_usdc REAL DEFAULT 0,
            setup_fee_usdc REAL DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            features TEXT,
            benefits TEXT,
            deliverables TEXT
        )
    """)
    con.commit()

    now = datetime.now(timezone.utc).isoformat()
    count = 0
    
    for p in PRODUCTS:
        tiers = p["tiers"]
        
        # If all 4 explicitly defined, use them
        if all(k in tiers for k in ("T1", "T2", "T3", "T4")):
            t1 = tiers.get("T1", 0)
            t2 = tiers.get("T2", 0)
            t3 = tiers.get("T3", 0)
            t4 = tiers.get("T4", 0)
        elif "T1" in tiers:
            # LeadFlow style: T1 defined, compute others from base
            t1 = tiers.get("T1", 0)
            t2 = tiers.get("T2", t1 * 2.5)
            t3 = tiers.get("T3", t1 * 5)
            t4 = tiers.get("T4", t1 * 10)
        elif "T2" in tiers:
            # LeadFlow T2 defined, work backwards/forwards
            t2 = tiers.get("T2", 0)
            t1 = tiers.get("T1", t2 / 2.5)
            t3 = tiers.get("T3", t2 * 2)
            t4 = tiers.get("T4", t2 * 4)
        elif "T3" in tiers:
            t3 = tiers.get("T3", 0)
            t1 = tiers.get("T1", t3 / 5)
            t2 = tiers.get("T2", t3 / 2)
            t4 = tiers.get("T4", t3 * 2)
        elif "T4" in tiers:
            t4 = tiers.get("T4", 0)
            t1 = tiers.get("T1", t4 / 10)
            t2 = tiers.get("T2", t4 / 4)
            t3 = tiers.get("T3", t4 / 2)
        elif "Monthly" in tiers:
            t1 = tiers["Monthly"]
            t2 = t1 * 2.5
            t3 = t1 * 5
            t4 = t1 * 10
        elif "Entry" in tiers:
            t1 = tiers["Entry"]
            t2 = t1 * 2.5
            t3 = t1 * 5
            t4 = t1 * 10
        elif "Scale" in tiers:
            t1 = tiers["Scale"]
            t2 = t1 * 2.5
            t3 = t1 * 5
            t4 = t1 * 10
        else:
            t1 = 0; t2 = 0; t3 = 0; t4 = 0
        
        con.execute(
            "INSERT OR REPLACE INTO si_products "
            "(sku, name, description, b2b_angle, "
            "tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, "
            "setup_fee_usdc, active, created_at, "
            "features, benefits, deliverables) "
            "VALUES (?,?,?,?,  ?,?,?,?,  ?,1,?,?,?,?)",
            (p["sku"], p["name"], p["description"], p["b2b_angle"],
             t1, t2, t3, t4,
             p["setup_fee_usdc"], now,
             p["features"], p["benefits"], p["deliverables"])
        )
        count += 1
        print(f"Seeded: {p['sku']} — {p['name']} (T1=${t1}, T2=${t2}, T3=${t3}, T4=${t4}, Setup=${p['setup_fee_usdc']})")

    con.commit()
    con.close()
    print(f"\nTotal seeded: {count} products")
    return count


if __name__ == "__main__":
    seed_products()