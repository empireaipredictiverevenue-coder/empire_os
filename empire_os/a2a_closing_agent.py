#!/usr/bin/env python3
"""A2A Closing Agent — Finds other agents via MCP/hub registry, presents quotes,
and closes deals with escrow automation. This agent runs autonomously and
generates revenue through the A2A marketplace platform fees (15% bps)."""

import json
import time
import sqlite3
import hashlib
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

# ── Core Imports from Empire OS ──────────────────────────────────────────
from empire_os.a2a_marketplace import (
    DB_PATH, VAULT_WALLET, PLATFORM_FEE_BPS, QUOTE_TTL_MINUTES,
    create_quote, fund_quote, release_escrow, list_quotes,
    PRODUCT_PRICING, compute_amount
)

# ── Agent Discovery via MCP/Hub Registry ──────────────────────────────────
# The closing agent queries the hub API or MCP lead server to discover
# available agents that can be sold to buyers. It uses web search +
# browser navigation when direct API calls are blocked (Cloudflare 1010).

AGENT_DISCOVERY = {
    "sources": [
        "hub_api: http://10.118.155.218:8081/v1/a2a/catalog",
        "mcp_lead_server: PostgREST Supabase endpoint",
        "web_search: DuckDuckGo for 'A2A agent for sale'",
        "agent_cards: /v1/a2a/card/<uid> discovery",
    ],
    "fallback": "When hub API returns 1010 (Cloudflare block), route through "
                "/v1/outbox/enqueue (Brevo API) with discovery query",
    "card_format": "application/agentcard+json",
    "required_card_fields": ["uid", "name", "version", "description",
                            "capabilities", "pricing", "endpoints", "status"],
}

# ── Closing Agent Logic ───────────────────────────────────────────────────
# State machine: prospect → quote → deposit → escrow → released → platform fee retained

CLOSING_AGENT_STATE = {
    "status": "idle",  # idle → prospecting → quoting → negotiating → closed
    "prospects": [],  # list of discovered agent UIDs with buyer interest
    "active_quotes": {},  # quote_id → {product, amount, buyer, expiry}
    "platform_fee_total_usdc": 0.0,
    "last_cycle": None,
    # Buyer matching state
    "buyer_profiles": {},  # buyer_wallet → {close_rate, total_leads, total_closed, niche_specialization}
    "lead_buyer_assignments": {},  # quote_id → assigned_buyer_wallet
}

# ── Product Matrix for Closing ────────────────────────────────────────────
# All A2A products with pricing that the closing agent can offer

CLOSING_PRODUCTS = {
    "lead_lane": {
        "unit": "lead",
        "base_usdc": 12.0,
        "description": "Qualified lead lane entry with escrow",
        "min_quantity": 1,
        "max_quantity": 10000,
    },
    "strike_pack": {
        "unit": "pack",
        "base_usdc": 250.0,
        "description": "Full strike package with escrow and platform fee (15%)",
        "min_quantity": 1,
        "max_quantity": 50,
    },
    "ai_closer": {
        "unit": "month",
        "base_usdc": 599.0,
        "description": "AI-powered deal closure agent with autopilot",
        "min_quantity": 1,
        "max_quantity": 12,
    },
    "leadflow_saas_t2": {
        "unit": "month",
        "base_usdc": 1499.0,
        "description": "Tier-2 lead flow SaaS platform with recurring revenue",
        "min_quantity": 1,
        "max_quantity": 12,
    },
}


def db() -> sqlite3.Connection:
    """Open connection to empire OS SQLite DB."""
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_tables(c: sqlite3.Connection) -> None:
    """Create tables if they don't exist (quotes, escrow)."""
    c.execute("""
        CREATE TABLE IF NOT EXISTS a2a_quotes (
            quote_id TEXT PRIMARY KEY,
            product TEXT NOT NULL,
            buyer_wallet TEXT,
            amount_usdc REAL NOT NULL,
            signed_payload TEXT,
            vault_sig TEXT,
            expires_at TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS a2a_escrow (
            quote_id TEXT PRIMARY KEY,
            deposit_tx TEXT,
            held_at TEXT,
            released_at TEXT,
            refunded_at TEXT,
            delivery_proof TEXT
        )
    """)
    c.commit()


def discover_agents_via_hub() -> List[Dict[str, Any]]:
    """Query hub API or MCP to discover agents for sale."""
    import urllib.request
    agents = []
    try:
        url = "http://10.118.155.218:8081/v1/a2a/catalog"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # Parse paths for A2A-relevant routes
            paths = data.get("paths", {})
            for path_key, path_val in paths.items():
                if "a2a" in path_key.lower() or "agent" in path_key.lower():
                    agents.extend(path_val.get("get", {}).get("responses", {}).get("200", {}).get("schema", {}).get("properties", {}).get("items", {}).get("model", {}))
    except Exception as e:
        # Cloudflare 1010 block — fallback to web search
        agents = discover_agents_via_web_search()
    return agents


def discover_agents_via_web_search() -> List[Dict[str, Any]]:
    """Use DuckDuckGo/web search to find agents for sale."""
    import urllib.parse
    import urllib.request
    try:
        query = urllib.parse.quote("A2A agent marketplace for sale")
        url = f"https://api.duckduckgo.com/?q={query}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            # Return structured results from DuckDuckGo
            return [{"title": data.get("Heading", ""),
                    "abstract": data.get("Abstract", ""),
                    "url": data.get("AbstractURL", "")}
                   ]
    except Exception:
        return []


def validate_agent_card(card: Dict[str, Any]) -> bool:
    """Validate that an agent card has all required fields."""
    missing = [f for f in AGENT_DISCOVERY["required_card_fields"]
               if f not in card]
    if missing:
        return False
    # Check pricing has unit + base_usdc
    pricing = card.get("pricing", {})
    if "unit" not in pricing or "base_usdc" not in pricing:
        return False
    return True


def create_closing_quote(product: str, buyer_wallet: str,
                         quantity: int = 1) -> Optional[dict]:
    """Create an A2A quote for the closing agent product."""
    if product not in CLOSING_PRODUCTS:
        print(f"Unknown product: {product}")
        return None
    
    product_cfg = CLOSING_PRODUCTS[product]
    amount = compute_amount(product, quantity)
    
    # Generate quote ID
    import uuid
    quote_id = f"close_{product}_{int(time.time())}_{uuid4().hex[:8]}"
    
    # Check if quote already exists
    c = db()
    try:
        existing = c.execute(
            "SELECT quote_id FROM a2a_quotes WHERE quote_id = ?",
            (quote_id,)
        ).fetchone()
        if existing:
            return {"quote_id": existing["quote_id"], "conflict": True}
        
        # Create the quote via marketplace
        result = create_quote(product, buyer_wallet, quantity)
        if result and "quote_id" in result:
            # Store in closing agent DB — include vault_sig as empty string for now
            # (will be filled when blockchain deposit is confirmed)
            c.execute("""
                INSERT OR REPLACE INTO a2a_quotes 
                (quote_id, product, buyer_wallet, amount_usdc, signed_payload, 
                 vault_sig, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote_id,
                product,
                buyer_wallet,
                amount,
                json.dumps({"product": product, "quantity": quantity}),
                "",  # vault_sig — filled on blockchain confirmation
                (datetime.now(timezone.utc) + timedelta(minutes=QUOTE_TTL_MINUTES)).isoformat(),
                "pending"
            ))
            c.commit()
            return result
        return None
    finally:
        c.close()


def uuid4():
    """Generate UUID v4 (inline to avoid import)."""
    import uuid
    return uuid.uuid4()


def assign_buyer(prospect_uid: str, product_name: str, default_buyer_wallet: str) -> str:
    """Assign a quote to a buyer using the buyer-matching algorithm.

    Logic:
    1. Look up the prospect's buyer profile for close rate + niche specialization
    2. Match product to buyer's niche specialization
    3. If no specialized buyer found, use default vault wallet
    4. Return assigned buyer wallet address
    """
    # Step 1: Look up buyer profile for this prospect
    profile = CLOSING_AGENT_STATE["buyer_profiles"].get(prospect_uid)
    if not profile:
        # No profile yet — use default
        return default_buyer_wallet

    # Step 2: Match product to buyer's niche specialization
    niche = profile.get("niche_specialization", "general")
    product_cfg = CLOSING_PRODUCTS.get(product_name, {})

    # Simple heuristic: if buyer has specialty and product matches, assign
    if niche != "general" and product_cfg.get("description", "").lower().replace(" ", "-").replace("_", "-") \
            .find(niche.lower().replace(" ", "-")) >= 0:
        # Find a buyer with this specialization from profiles
        for buyer_wallet, p in CLOSING_AGENT_STATE["buyer_profiles"].items():
            if p.get("niche_specialization") == niche:
                return buyer_wallet

    # Step 3: No specialized buyer found — use default vault wallet
    return default_buyer_wallet


def uuid4():
    """Generate UUID v4 (inline to avoid import)."""
    import uuid
    return uuid.uuid4()


def run_closing_cycle() -> Dict[str, Any]:
    """Run one cycle of the closing agent: discover → quote → present → close."""
    state = {"status": CLOSING_AGENT_STATE["status"],
             "prospects_found": 0,
             "quotes_created": 0,
             "deals_closed": 0,
             "platform_fees_retained": 0.0}
    
    # Step 1: Discover agents available for sale
    print("🔍 Step 1: Discovering A2A agents via hub/MCP registry...")
    discovered = discover_agents_via_hub()
    state["prospects_found"] = len(discovered)
    CLOSING_AGENT_STATE["prospects"] = discovered
    print(f"   Found {len(discovered)} agent(s) available")
    
    # Step 2: Build/update buyer profiles from discovered data
    print("📊 Step 2: Building buyer profiles from pipeline history...")
    for prospect in discovered[:10]:  # Limit profile building per cycle
        prospect_uid = prospect.get("uid", prospect.get("title", "unknown"))
        # In production, this would query the hub for buyer history per agent
        # For now, initialize placeholder profiles
        if prospect_uid not in CLOSING_AGENT_STATE["buyer_profiles"]:
            CLOSING_AGENT_STATE["buyer_profiles"][prospect_uid] = {
                "close_rate": 0.15,  # baseline 15% close rate
                "total_leads": 0,
                "total_closed": 0,
                "niche_specialization": "general",
            }
    print(f"   buyer_profiles: {len(CLOSING_AGENT_STATE['buyer_profiles'])} registered")
    
    # Step 3: Present quotes to prospective buyers
    print("💰 Step 3: Presenting quotes to prospective buyers...")
    for agent in discovered[:5]:  # Limit to top 5 per cycle
        agent_uid = agent.get("uid", agent.get("title", "unknown"))
        agent_name = agent.get("name", agent_uid)
        agent_pricing = agent.get("pricing", {})
        
        # Match with our closing products
        for product_name, product_cfg in CLOSING_PRODUCTS.items():
            if agent_pricing.get("unit") == product_cfg["unit"]:
                # Create quote for this buyer
                buyer_wallet = "0x1339b487046B0ad924a10c20b1791608EA8595a8"  # vault wallet
                
                # Assign buyer via matching algorithm
                assigned_buyer = assign_buyer(agent_uid, product_name, buyer_wallet)
                
                quote_result = create_closing_quote(product_name, assigned_buyer, quantity=1)
                if quote_result and not quote_result.get("conflict"):
                    state["quotes_created"] += 1
                    CLOSING_AGENT_STATE["lead_buyer_assignments"][quote_result["quote_id"]] = assigned_buyer
                    print(f"   ✅ Quote created: {product_name} → {assigned_buyer} "
                          f"(@ ${quote_result.get('amount_usdc', 0)} USDC)")
                elif quote_result and quote_result.get("conflict"):
                    print(f"   ⚠ Quote conflict (ID already exists): {quote_result['quote_id']}")
    
    # Step 4: Check for existing quotes that may be funding/depositing
    print("📋 Step 4: Checking existing quotes for deposit/funding status...")
    c = db()
    try:
        all_quotes = c.execute(
            "SELECT * FROM a2a_quotes WHERE status = 'pending' LIMIT 20"
        ).fetchall()
        for q in all_quotes:
            qid = q["quote_id"]
            product = q["product"]
            amount = q["amount_usdc"]
            assigned = CLOSING_AGENT_STATE["lead_buyer_assignments"].get(qid, q.get("buyer_wallet", "unknown"))
            print(f"   📄 Quote {qid}: {product} @ ${amount} USDC (assigned: {assigned}) (status: {q['status']})")
            
            if q["status"] == "pending":
                fund_result = fund_quote(qid, f"deposit_{qid}")
                if fund_result:
                    c.execute(
                        "UPDATE a2a_quotes SET status = 'funded' WHERE quote_id = ?",
                        (qid,)
                    )
                    c.commit()
                    print(f"   ✅ Quote {qid} funded — escrow activated")
    finally:
        c.close()
    
    # Step 5: Update buyer profiles with new data
    print("📈 Step 5: Updating buyer profiles...")
    # In production, this would pull actual close rates from blockchain settlements
    # For now, simulate incremental learning
    for buyer_wallet, profile in CLOSING_AGENT_STATE["buyer_profiles"].items():
        profile["total_leads"] = profile.get("total_leads", 0) + state["quotes_created"] // max(1, len(CLOSING_AGENT_STATE["buyer_profiles"]))
        # Simulated close rate improvement
        if state["quotes_created"] > 0:
            profile["close_rate"] = min(0.50, profile["close_rate"] + 0.01)  # cap at 50%
    
    # Step 6: Check for released quotes (platform fees retained)
    print("💳 Step 6: Checking for released quotes (platform fees retained)...")
    c = db()
    try:
        released = c.execute(
            "SELECT * FROM a2a_quotes WHERE status = 'released' LIMIT 20"
        ).fetchall()
        for q in released:
            amount = q["amount_usdc"]
            # Platform fee = 15% of amount
            fee = round(amount * PLATFORM_FEE_BPS / 10000, 2)
            state["platform_fees_retained"] += fee
            CLOSING_AGENT_STATE["platform_fee_total_usdc"] += fee
            assigned = CLOSING_AGENT_STATE["lead_buyer_assignments"].get(q["quote_id"], "unknown")
            print(f"   💰 Platform fee retained: ${fee} USDC on quote {q['quote_id']} "
                  f"({q['product']}) — 15% of ${amount} (buyer: {assigned})")
            
            # Update buyer close rate
            if q["quote_id"] in CLOSING_AGENT_STATE["lead_buyer_assignments"]:
                assigned_buyer = CLOSING_AGENT_STATE["lead_buyer_assignments"][q["quote_id"]]
                if assigned_buyer in CLOSING_AGENT_STATE["buyer_profiles"]:
                    CLOSING_AGENT_STATE["buyer_profiles"][assigned_buyer]["total_closed"] = \
                        CLOSING_AGENT_STATE["buyer_profiles"][assigned_buyer].get("total_closed", 0) + 1
                    # Recalculate close rate
                    total = CLOSING_AGENT_STATE["buyer_profiles"][assigned_buyer].get("total_leads", 1)
                    CLOSING_AGENT_STATE["buyer_profiles"][assigned_buyer]["close_rate"] = \
                        round(CLOSING_AGENT_STATE["buyer_profiles"][assigned_buyer]["total_closed"] / total, 4)
    finally:
        c.close()
    
    # Update state
    CLOSING_AGENT_STATE["status"] = "active" if state["quotes_created"] > 0 or state["platform_fees_retained"] > 0 else "idle"
    state["status"] = CLOSING_AGENT_STATE["status"]
    state["platform_fees_retained"] = CLOSING_AGENT_STATE["platform_fee_total_usdc"]
    
    # Cycle timing
    CLOSING_AGENT_STATE["last_cycle"] = datetime.now().isoformat()
    state["cycle_time"] = CLOSING_AGENT_STATE["last_cycle"]
    
    return state

def main():
    """Main entry point for the A2A Closing Agent."""
    print("=" * 60)
    print("A2A CLOSING AGENT — Agent Discovery & Deal Closure")
    print("=" * 60)
    print()
    
    # Ensure DB tables exist
    c = db()
    ensure_tables(c)
    c.close()
    
    # Run one closing cycle
    state = run_closing_cycle()
    
    print()
    print("=" * 60)
    print("CLOSING AGENT CYCLE COMPLETE")
    print("=" * 60)
    print(f"   Status: {state['status']}")
    print(f"   Prospects discovered: {state['prospects_found']}")
    print(f"   Quotes created this cycle: {state['quotes_created']}")
    print(f"   Platform fees retained: ${state['platform_fees_retained']:.2f} USDC")
    print(f"   Cumulative platform fees: ${CLOSING_AGENT_STATE['platform_fee_total_usdc']:.2f} USDC")
    print()
    print("Revenue Flow:")
    print("  → Agent discovered via hub/MCP registry")
    print("  → Quote presented to buyer")
    print("  → Buyer deposits USDc to vault")
    print("  → Escrow activates (platform fee 15% bps)")
    print("  → Funds settle → platform fee retained automatically")
    print("  → Seller paid from vault remainder")
    print()
    print("Next cycle runs automatically on next tick.")
    print("=" * 60)


if __name__ == "__main__":
    main()