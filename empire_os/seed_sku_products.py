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

# sku -> (name, setup_fee_usdc)
# Parsed from pricing.md "DB SKUs" block. Tiers are T1/T2/T3/T4(titanium).
SKUS = {
    "empire_leads_engine": ("Empire Leads Engine", 10000),
    "hermes_framework":    ("Hermes Framework", 8000),
    "opencut_studio":      ("OpenCut Studio", 5000),
    "empire_templates":    ("Empire Templates", 3000),
    "marketingskills":     ("MarketingSkills", 3000),
    "satellite_idle_watch":("Satellite Idle Watch", 0),
    "skillspector_audit":  ("SkillSpector Audit", 0),
    "synthetic_agent":     ("Synthetic Agent", 10000),
    "aeo_monitor":         ("AEO Monitor", 0),
    "agent_copilot":       ("Agent Co-Pilot", 3000),
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
    # match lines like:  "  - empire_leads_engine: 199 / 599 / 1999 / 5999   (setup $10,000)"
    pat = re.compile(
        r"-\s*([a-z0-9_]+):\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)"
        r"(?:\s*\(setup\s*\$?([\d,]+)\))?", re.I)
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
        return 2
    text = PRICING.read_text()
    parsed = parse_block(text)

    con = sqlite3.connect(DB)
    con.execute(
        """CREATE TABLE IF NOT EXISTS si_products (
            sku TEXT PRIMARY KEY, name TEXT, repo_url TEXT, license TEXT,
            description TEXT, b2b_angle TEXT,
            tier1_usdc REAL, tier2_usdc REAL, tier3_usdc REAL, tier4_usdc REAL,
            setup_fee_usdc REAL, active INTEGER, created_at TEXT)""")
    now = datetime.now(timezone.utc).isoformat()
    n = 0
    for sku, (name, setup_md) in SKUS.items():
        p = parsed.get(sku)
        if not p:
            print(f"  skip {sku}: not found in pricing.md block")
            continue
        # trust pricing.md block tiers; fall back to SKUS default setup
        setup = p["setup"] if p["setup"] else setup_md
        con.execute(
            "INSERT OR REPLACE INTO si_products "
            "(sku, name, repo_url, license, description, b2b_angle, "
            "tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, setup_fee_usdc, "
            "active, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)",
            (sku, name, "", "", f"{name} — Empire OS marketplace SKU",
             "B2B lead-gen / agent commerce",
             p["t1"], p["t2"], p["t3"], p["t4"], setup, now))
        n += 1
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM si_products WHERE active=1").fetchone()[0]
    con.close()
    print(f"Seeded {n} SKUs into si_products (active total now: {total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
