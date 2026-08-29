#!/usr/bin/env python3
"""
Create new revenue products targeting gaps in the current catalog.
Products map to high-revenue niches + new verticals from the Master Spec v7.0.
"""
import sqlite3, json
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"

NEW_PRODUCTS = [
    {
        "sku": "empire_traffic_arbitrage",
        "name": "Empire Traffic Arbitrage Engine",
        "repo_url": "",
        "license": "proprietary",
        "description": "Real-time multi-niche ad spend optimization engine. Shifts traffic to highest-margin verticals automatically. Includes traffic_router with margin analysis.",
        "b2b_angle": "Traffic arbitrage / ad spend optimization",
        "tier1_usdc": 299.0,
        "tier2_usdc": 799.0,
        "tier3_usdc": 2499.0,
        "tier4_usdc": 7999.0,
        "setup_fee_usdc": 5000.0,
        "features": json.dumps(["Real-time margin analysis", "Multi-niche traffic routing", "Ad spend auto-rebalance", "Conversion tracking", "PostHog telemetry integration"]),
        "benefits": json.dumps(["Cut wasted ad spend by 40%+", "Auto-shift budget to winning niches", "Sub-minute routing decisions"]),
        "deliverables": json.dumps(["traffic_router.js", "margin dashboard", "API access"]),
    },
    {
        "sku": "empire_scraper_pro",
        "name": "Empire Scraper Pro",
        "repo_url": "",
        "license": "proprietary",
        "description": "Multi-threaded native scraping engine with proxy rotation and rate limiting. Extracts structured data from any vertical. Feeds Pinecone vectors + Twenty CRM.",
        "b2b_angle": "B2B data extraction / lead mining",
        "tier1_usdc": 199.0,
        "tier2_usdc": 599.0,
        "tier3_usdc": 1999.0,
        "tier4_usdc": 5999.0,
        "setup_fee_usdc": 3000.0,
        "features": json.dumps(["Multi-threaded scraping", "Proxy rotation pool", "Rate limiting", "Structured data output", "Twenty CRM sync", "Pinecone vector ingestion"]),
        "benefits": json.dumps(["10x faster than manual scraping", "No IP bans", "Structured JSON output", "Real-time CRM sync"]),
        "deliverables": json.dumps(["empire_scraper_core.js", "proxy config", "API docs"]),
    },
    {
        "sku": "empire_red_team",
        "name": "Empire Red Team Evaluator",
        "repo_url": "",
        "license": "proprietary",
        "description": "Adversarial evaluation loop that stress-tests data payloads against buyer profiles. Auto-patches toxic vectors. Gauntlet Loop workflow with binary pass/fail.",
        "b2b_angle": "Data quality assurance / adversarial validation",
        "tier1_usdc": 149.0,
        "tier2_usdc": 449.0,
        "tier3_usdc": 1499.0,
        "tier4_usdc": 4499.0,
        "setup_fee_usdc": 2000.0,
        "features": json.dumps(["Adversarial buyer profile testing", "Toxic vector detection", "Auto-patch recommendations", "Gauntlet Loop workflow", "PostHog feedback integration"]),
        "benefits": json.dumps(["Catch bad data before buyers see it", "Improve lead quality scores", "Reduce refund/chargeback rate"]),
        "deliverables": json.dumps(["red_team_loop.js", "telemetry_feedback.js", "evaluation reports"]),
    },
    {
        "sku": "empire_mcp_gateway",
        "name": "Empire MCP Gateway",
        "repo_url": "",
        "license": "proprietary",
        "description": "Fastify MCP server with HTTP 402 payment intents, IP+token rate limiting, /healthz heartbeat, and agentic query routing. Cloudflare-edge protected.",
        "b2b_angle": "MCP protocol gateway / API monetization",
        "tier1_usdc": 99.0,
        "tier2_usdc": 299.0,
        "tier3_usdc": 999.0,
        "tier4_usdc": 2999.0,
        "setup_fee_usdc": 1500.0,
        "features": json.dumps(["MCP protocol support", "HTTP 402 payment intents", "IP + token rate limiting", "/healthz heartbeat (30s)", "Cloudflare WAF integration", "Agentic query routing", "llms.txt auto-generation"]),
        "benefits": json.dumps(["Monetize any AI query", "Enterprise-grade security", "Sub-100ms response via edge cache", "Auto-scaling ready"]),
        "deliverables": json.dumps(["server.js", "intent_tracker.js", "generate_llms_txt.js", "Docker config"]),
    },
    {
        "sku": "empire_vector_cache",
        "name": "Empire Vector Cache",
        "repo_url": "",
        "license": "proprietary",
        "description": "Redis-powered 10-minute vector response cache layer. Eliminates redundant Pinecone queries. Drops latency from 300ms to 5ms for cached responses.",
        "b2b_angle": "Vector DB optimization / latency reduction",
        "tier1_usdc": 49.0,
        "tier2_usdc": 149.0,
        "tier3_usdc": 499.0,
        "tier4_usdc": 1499.0,
        "setup_fee_usdc": 500.0,
        "features": json.dumps(["Redis 10-min TTL cache", "Pinecone pre-check", "Cache invalidation hooks", "Hit/miss metrics", "Auto-warm frequently queried vectors"]),
        "benefits": json.dumps(["60x latency reduction on cache hits", "Cut Pinecone API costs", "Handle traffic spikes gracefully"]),
        "deliverables": json.dumps(["redis_cache.js", "vector_ingest.js", "monitoring dashboard"]),
    },
    {
        "sku": "empire_plumbing_leads",
        "name": "Empire Plumbing Lead Stream",
        "repo_url": "",
        "license": "proprietary",
        "description": "Dedicated plumbing lead delivery pipeline. Real-time buyer matching for plumbing niche. Currently delivering 12K+ leads at $483K pipeline value.",
        "b2b_angle": "Plumbing lead generation / pay-per-lead",
        "tier1_usdc": 199.0,
        "tier2_usdc": 599.0,
        "tier3_usdc": 1999.0,
        "tier4_usdc": 5999.0,
        "setup_fee_usdc": 0.0,
        "features": json.dumps(["Real-time lead delivery", "Buyer endpoint integration", "USDT BEP20 settlement", "Lead scoring + grading", "Auto-retry on delivery failure"]),
        "benefits": json.dumps(["Immediate lead flow", "Pay only for delivered leads", "USDT crypto settlement", "No long-term contract"]),
        "deliverables": json.dumps(["Webhook endpoint", "Lead API access", "Settlement dashboard"]),
    },
    {
        "sku": "empire_roofing_leads",
        "name": "Empire Roofing Lead Stream",
        "repo_url": "",
        "license": "proprietary",
        "description": "Dedicated roofing lead delivery pipeline. Currently delivering 1.4K+ leads at $77K pipeline value across roof_repair + residential_roofing niches.",
        "b2b_angle": "Roofing lead generation / pay-per-lead",
        "tier1_usdc": 199.0,
        "tier2_usdc": 599.0,
        "tier3_usdc": 1999.0,
        "tier4_usdc": 5999.0,
        "setup_fee_usdc": 0.0,
        "features": json.dumps(["Real-time lead delivery", "Roofing niche specialization", "Storm damage detection", "Satellite imagery integration", "USDT BEP20 settlement"]),
        "benefits": json.dumps(["High-value roofing leads", "Storm event triggers", "Satellite damage assessment", "Pay per delivered lead"]),
        "deliverables": json.dumps(["Webhook endpoint", "Lead API", "Storm alert integration"]),
    },
    {
        "sku": "empire_contractor_leads",
        "name": "Empire General Contractor Lead Stream",
        "repo_url": "",
        "license": "proprietary",
        "description": "Dedicated general contractor lead delivery pipeline. Currently delivering 19K+ leads at $435K pipeline value. Largest niche by volume.",
        "b2b_angle": "General contractor lead generation / pay-per-lead",
        "tier1_usdc": 199.0,
        "tier2_usdc": 599.0,
        "tier3_usdc": 1999.0,
        "tier4_usdc": 5999.0,
        "setup_fee_usdc": 0.0,
        "features": json.dumps(["Real-time lead delivery", "Multi-trade contractor matching", "USDT BEP20 settlement", "Lead scoring + grading", "Volume: 247K+ pending supply"]),
        "benefits": json.dumps(["Largest lead volume niche", "Consistent daily delivery", "Pay per delivered lead", "Crypto settlement"]),
        "deliverables": json.dumps(["Webhook endpoint", "Lead API", "Volume dashboard"]),
    },
    {
        "sku": "empire_mass_tort_leads",
        "name": "Empire Mass Tort Lead Stream",
        "repo_url": "",
        "license": "proprietary",
        "description": "High-value mass tort / class action lead generation. $5K-$50K per qualified case. Legal compliance screening included.",
        "b2b_angle": "Legal mass tort lead generation / per-case pricing",
        "tier1_usdc": 499.0,
        "tier2_usdc": 1499.0,
        "tier3_usdc": 4999.0,
        "tier4_usdc": 14999.0,
        "setup_fee_usdc": 0.0,
        "features": json.dumps(["Mass tort case detection", "Legal compliance screening", "Per-case pricing ($5K-$50K)", "Attorney buyer matching", "USDT BEP20 settlement"]),
        "benefits": json.dumps(["Highest value per lead", "Pre-screened for legal compliance", "Direct attorney matching", "Crypto settlement"]),
        "deliverables": json.dumps(["Case intake API", "Compliance screening", "Attorney matching dashboard"]),
    },
    {
        "sku": "empire_restoration_leads",
        "name": "Empire Restoration Lead Stream",
        "repo_url": "",
        "license": "proprietary",
        "description": "Water/fire damage restoration lead delivery. Storm-event triggered. Satellite imagery + weather signal integration for proactive outreach.",
        "b2b_angle": "Restoration lead generation / storm-triggered",
        "tier1_usdc": 299.0,
        "tier2_usdc": 899.0,
        "tier3_usdc": 2999.0,
        "tier4_usdc": 8999.0,
        "setup_fee_usdc": 0.0,
        "features": json.dumps(["Storm event triggers", "Satellite damage detection", "Restoration company matching", "USDT BEP20 settlement", "Weather signal integration"]),
        "benefits": json.dumps(["First-mover on storm events", "Satellite-verified damage", "Direct restoration company matching"]),
        "deliverables": json.dumps(["Storm alert API", "Damage assessment reports", "Lead delivery webhook"]),
    },
    {
        "sku": "empire_pay_per_call",
        "name": "Empire Pay-Per-Call Router",
        "repo_url": "",
        "license": "proprietary",
        "description": "Pay-per-call routing engine. Routes inbound calls to highest-bidding buyer in real time. Telephony webhook integration with call tracking.",
        "b2b_angle": "Pay-per-call / call routing / telephony",
        "tier1_usdc": 299.0,
        "tier2_usdc": 899.0,
        "tier3_usdc": 2999.0,
        "tier4_usdc": 8999.0,
        "setup_fee_usdc": 5000.0,
        "features": json.dumps(["Real-time call routing", "Bid-based buyer selection", "Call tracking + recording", "Telephony webhook (port 9100)", "USDT BEP20 settlement"]),
        "benefits": json.dumps(["Revenue per call, not per lead", "Multi-buyer bidding war", "Call analytics dashboard"]),
        "deliverables": json.dumps(["Telephony webhook", "Call routing API", "Analytics dashboard"]),
    },
    {
        "sku": "empire_cortex_v4",
        "name": "Empire Cortex V4 Intelligence",
        "repo_url": "",
        "license": "proprietary",
        "description": "Enterprise-grade predictive revenue intelligence system. Revenue forecasting, gap detection, leak analysis, and waste elimination across all verticals.",
        "b2b_angle": "Predictive intelligence / revenue optimization",
        "tier1_usdc": 499.0,
        "tier2_usdc": 1499.0,
        "tier3_usdc": 4999.0,
        "tier4_usdc": 14999.0,
        "setup_fee_usdc": 10000.0,
        "features": json.dumps(["Revenue forecasting", "Market gap detection", "Revenue leak analysis", "Waste elimination", "Ollama LLM integration", "Predictive dashboard"]),
        "benefits": json.dumps(["See revenue 30 days ahead", "Auto-detect leaks before they cost you", "Optimize agent fleet allocation", "AI-powered strategy recommendations"]),
        "deliverables": json.dumps(["Cortex engine", "Predictive dashboard", "Alert system"]),
    },
]

def create_products():
    conn = sqlite3.connect(DB, timeout=30, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=20000")
    conn.row_factory = sqlite3.Row

    created = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for p in NEW_PRODUCTS:
        # Check if SKU exists
        existing = conn.execute("SELECT sku FROM si_products WHERE sku=?", (p["sku"],)).fetchone()
        if existing:
            print(f"  SKIP (exists): {p['sku']}")
            skipped += 1
            continue

        cols = ["sku", "name", "repo_url", "license", "description", "b2b_angle",
                "tier1_usdc", "tier2_usdc", "tier3_usdc", "tier4_usdc", "setup_fee_usdc",
                "active", "created_at", "features", "benefits", "deliverables"]
        vals = [p["sku"], p["name"], p["repo_url"], p["license"], p["description"], p["b2b_angle"],
                p["tier1_usdc"], p["tier2_usdc"], p["tier3_usdc"], p["tier4_usdc"], p["setup_fee_usdc"],
                1, now, p["features"], p["benefits"], p["deliverables"]]

        placeholders = ",".join("?" * len(cols))
        conn.execute(f"INSERT INTO si_products ({','.join(cols)}) VALUES ({placeholders})", vals)
        print(f"  CREATED: {p['sku']} | {p['name']} | T1=${p['tier1_usdc']} T4=${p['tier4_usdc']} | setup=${p['setup_fee_usdc']}")
        created += 1

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM si_products WHERE active=1").fetchone()[0]
    print(f"\nTotal active products: {total} (created={created}, skipped={skipped})")

    # Revenue potential if all tiers sold at T2
    rows = conn.execute("SELECT sku, name, tier2_usdc FROM si_products WHERE active=1 ORDER BY tier2_usdc DESC").fetchall()
    monthly_if_10_each = sum(r[2] * 10 for r in rows)
    print(f"If 10 subs each at Tier 2: ${monthly_if_10_each:.0f}/mo MRR")

    conn.close()
    return created

if __name__ == "__main__":
    create_products()
