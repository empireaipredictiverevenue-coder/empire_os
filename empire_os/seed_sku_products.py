#!/usr/bin/env python3
"""Seed si_products from g-brain/revenue/pricing.md (12-SKU tiers).

Parses the "DB SKUs" block of pricing.md and writes rows into si_products
so /v1/products/pricing serves the real marketplace catalog (not just the
hardcoded PRODUCT_PRICES). Idempotent: INSERT OR REPLACE by sku.

Run:  /root/venv/bin/python3 empire_os/seed_sku_products.py
"""
from __future__ import annotations
import re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/empire_os")
DB = ROOT / "empire_os.db"
PRICING = Path("/root/g-brain/revenue/pricing.md")

# sku -> (name, setup_fee_usdc)  — ALL setup fees $0 for initial traction
SKUS = {
    "empire_leads_engine": ("Empire Leads Engine", 0),
    "hermes_framework":    ("Hermes Framework", 0),
    "opencut_studio":      ("OpenCut Studio", 0),
    "empire_templates":    ("Empire Templates", 0),
    "marketingskills":     ("MarketingSkills", 0),
    "satellite_idle_watch":("Satellite Idle Watch", 0),
    "skillspector_audit":  ("SkillSpector Audit", 0),
    "synthetic_agent":     ("Synthetic Agent", 0),
    "aeo_monitor":         ("AEO Monitor", 0),
    "agent_copilot":       ("Agent Co-Pilot", 0),
}
# T1 base prices (USDC/mo) from pricing.md; T2=x2.5 T3=x5 T4=x10
T1 = {
    "empire_leads_engine": 199, "hermes_framework": 149, "opencut_studio": 99,
    "empire_templates": 59, "marketingskills": 39, "satellite_idle_watch": 99,
    "skillspector_audit": 79, "synthetic_agent": 199, "aeo_monitor": 29,
    "agent_copilot": 99,
}


def parse_block(text: str) -> dict:
    """Extract per-sku T1..T4 + setup from the DB SKUs block."""
    out = {}
    pat = re.compile(
        r"--\s*([a-z0-9_]+):\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)"
        r"(?:\s*\(\s*setup\s*\$?([\d,]+)?\s*\))?", re.I)
    for m in pat.finditer(text):
        sku, t1, t2, t3, t4, setup = m.groups()
        out[sku] = {
            "t1": float(t1), "t2": float(t2), "t3": float(t3), "t4": float(t4),
            "setup": float(setup.replace(",", "")) if setup else 0.0,
        }
    return out


def main() -> int:
    if not PRICING.exists():
        print(f"ERROR: pricing.md not found at {PRICING}")
        return 1

    text = PRICING.read_text()
    parsed = parse_block(text)

    con = sqlite3.connect(str(DB), timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    count = 0

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
    for sku, (name, setup) in SKUS.items():
        p = parsed.get(sku, {})
        t1 = p.get("t1", T1.get(sku, 0))
        t2 = p.get("t2", t1 * 2.5)
        t3 = p.get("t3", t1 * 5)
        t4 = p.get("t4", t1 * 10)
        s = p.get("setup", setup)
        desc = f"{name} -- Empire OS marketplace SKU"
        con.execute(
            "INSERT OR REPLACE INTO si_products "
            "(sku, name, description, b2b_angle, "
            "tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, "
            "setup_fee_usdc, active, created_at) "
            "VALUES (?,?,?,?,  ?,?,?,?,  ?,1,?)",
            (sku, name, desc, "B2B lead-gen / agent commerce",
             t1, t2, t3, t4, s, now))
        count += 1

    con.commit()
    con.close()
    print(f"Seeded {count} products (all setup fees $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
