#!/usr/bin/env python3
"""a2a_discovery — Google A2A-protocol AgentCard + peer registry.

Makes Empire's A2A marketplace DISCOVERABLE by other agents:
  - build_agent_card()  -> spec-compliant AgentCard JSON (schemaVersion 0.2.0)
  - Served at /.well-known/agent.json and /v1/a2a/agent-card
  - Peer registry: other agents can register their cards so WE can call THEM
    (a2a_known_agents table). Two-way agent2agent.

Skills in the card map 1:1 to marketplace products (each is a callable
A2A service with a signed-quote + escrow settlement flow).
"""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
VAULT_WALLET = os.getenv("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
AGENT_URL = os.getenv("AGENT_BASE_URL", "http://216.128.149.56:8081")
AGENT_VERSION = os.getenv("AGENT_VERSION", "4.0.0")

# Human-readable skill copy. Keys mirror PRODUCT_CATALOG in hub.py.
SKILL_BLURB = {
    "lead_lane": "Exclusive pay-per-lead lane locked to a niche+metro. USDT settlement.",
    "satellite_wastage": "Idle-asset / logistics wastage monitor report from satellite intel.",
    "warehouse_asset": "Warehouse inventory + asset reporting feed (monthly).",
    "strike_pack": "Tiered emergency lead burst for a niche/metro event.",
    "ai_closer": "AI deal-closure agent — closes your pipeline, settles in USDT.",
    "leadflow_saas_t2": "Enterprise lead qualification + AI scoring + automated outreach.",
    "imperium_conversion_os": "Full revenue loop: crawler -> segmentation -> buyer push -> USDT.",
    "empire_os_v4_beta": "Self-driving empire ops: scraping, scoring, marketplace, settlement.",
    "deep_intel_report": "AI competitor + revenue-leak analysis, delivered as PDF in 24h.",
    "lead_pack_50": "50 exclusive Omega-scored leads (emails+phones), 48h delivery.",
    "lead_pack_250": "250 exclusive Omega-scored leads (emails+phones), 72h delivery.",
    "serp_sweep_100": "100 hiring/expansion-intent businesses discovered via SERP, 24h.",
    "serp_sweep_250": "250 hiring/expansion-intent businesses discovered via SERP, 48h.",
    "serp_lane_feeder": "Weekly automated SERP intent sweep feeding your exclusive lane.",
    "seo_audit_report": "5-page technical SEO audit, score /100, delivered 1h.",
    "seo_content_brief": "Landing-page content brief from real autocomplete demand, 1h.",
    "cortex_blueprint_pack": "AI campaign blueprints: heat score, visual DNA, script DNA.",
}


def build_agent_card(catalog: dict, prices: dict) -> dict:
    """Return a Google-A2A-spec AgentCard describing Empire's A2A services."""
    skills = []
    for sku, desc in catalog.items():
        price = prices.get(sku)
        skills.append({
            "id": sku,
            "name": sku.replace("_", " ").title(),
            "description": SKILL_BLURB.get(sku, desc),
            "tags": ["b2b", "leads", "usdt", "escrow", sku.split("_")[0]],
            "examples": [
                f"Quote {sku} for 1 unit",
                f"Buy {sku} and provision access",
            ],
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
            "endpoints": {
                "quote": f"{AGENT_URL}/v1/a2a/quote",
                "get": f"{AGENT_URL}/v1/a2a/quote/{{quote_id}}",
                "catalog": f"{AGENT_URL}/v1/a2a/catalog",
                "pay": f"{AGENT_URL}/v1/pay/{{memo}}",
                "price_usdc": price,
            },
        })

    return {
        "schemaVersion": "0.2.0",
        "name": "Empire OS A2A Marketplace",
        "description": (
            "Autonomous B2B agent marketplace. Buy leads, AI closers, SEO intel and "
            "revenue-ops SaaS via signed quote + BSC-USDT escrow. Settlement on-chain, "
            "access provisioned automatically on release."
        ),
        "url": AGENT_URL,
        "provider": {
            "organization": "Empire AI",
            "url": "https://empire-ai.co.uk",
        },
        "version": AGENT_VERSION,
        "documentationUrl": "https://empire-ai.co.uk/docs/a2a",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "authentication": {
            "schemes": ["Bearer"],
            "description": "Buyer wallet address supplied as Bearer token / X-Buyer-Wallet header.",
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": skills,
        "settlement": {
            "network": "bsc",
            "asset": "USDT",
            "vault": VAULT_WALLET,
            "flow": "signed_quote -> deposit(memo=a2a:<quote_id>) -> escrow_held -> release -> seat",
        },
    }


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_registry(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS a2a_known_agents (
            agent_id TEXT PRIMARY KEY,
            card_url TEXT,
            name TEXT,
            org TEXT,
            base_url TEXT,
            card_json TEXT,
            last_seen TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    c.commit()


def register_peer(agent_id: str, card: dict, card_url: str = "") -> dict:
    """Record a remote agent's AgentCard so WE can call it (inbound A2A)."""
    c = db()
    try:
        ensure_registry(c)
        base = card.get("url", "")
        c.execute(
            """INSERT OR REPLACE INTO a2a_known_agents
               (agent_id, card_url, name, org, base_url, card_json, last_seen, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            (agent_id, card_url, card.get("name", ""),
             (card.get("provider") or {}).get("organization", ""),
             base, json.dumps(card), _now(), "active"),
        )
        c.commit()
        return {"ok": True, "agent_id": agent_id}
    finally:
        c.close()


def list_peers(status: str = "active") -> list:
    c = db()
    try:
        ensure_registry(c)
        rows = c.execute(
            "SELECT * FROM a2a_known_agents WHERE status=? ORDER BY last_seen DESC",
            (status,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
