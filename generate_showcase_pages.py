#!/usr/bin/env python3
"""Generate showcase HTML pages for all products using product_spec.py."""
import sys
sys.path.insert(0, "/root/empire_os")
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
import product_spec as ps

DB = Path("/root/empire_os/empire_os.db")
SURFACE_ROOT = Path("/tmp/empire_products")

def main():
    con = sqlite3.connect(str(DB), timeout=30)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM si_products WHERE active=1 ORDER BY tier1_usdc DESC").fetchall()
    con.close()
    
    SURFACE_ROOT.mkdir(parents=True, exist_ok=True)
    count = 0
    
    for row in rows:
        spec = dict(row)
        # Build spec dict for product_spec.showcase_html
        tier_dict = {}
        if spec["tier1_usdc"]: tier_dict["T1"] = spec["tier1_usdc"]
        if spec["tier2_usdc"]: tier_dict["T2"] = spec["tier2_usdc"]
        if spec["tier3_usdc"]: tier_dict["T3"] = spec["tier3_usdc"]
        if spec["tier4_usdc"]: tier_dict["T4"] = spec["tier4_usdc"]
        
        spec_dict = {
            "sku": spec["sku"],
            "name": spec["name"],
            "tagline": spec.get("b2b_angle", ""),
            "description": spec["description"],
            "tech": "Empire OS predictive stack",
            "specs": [
                ("Tier 1 (mo)", f"${spec['tier1_usdc']:,.0f}/mo") if spec['tier1_usdc'] else None,
                ("Tier 2 (mo)", f"${spec['tier2_usdc']:,.0f}/mo") if spec['tier2_usdc'] else None,
                ("Tier 3 (mo)", f"${spec['tier3_usdc']:,.0f}/mo") if spec['tier3_usdc'] else None,
                ("Tier 4 (mo)", f"${spec['tier4_usdc']:,.0f}/mo") if spec['tier4_usdc'] else None,
                ("Setup Fee", f"${spec['setup_fee_usdc']:,.0f}") if spec['setup_fee_usdc'] else None,
            ],
            "tiers": tier_dict,
            "cta_url": f"/v1/buyers/signup-seat?sku={spec['sku']}",
            "settled": "USDC (BSC/TS-5)",
        }
        # Filter None specs
        spec_dict["specs"] = [s for s in spec_dict["specs"] if s]
        
        try:
            html = ps.showcase_html(spec_dict)
            out_dir = SURFACE_ROOT / "products" / row["sku"]
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(html)
            count += 1
            print(f"Generated: {row['sku']} -> {out_dir}/index.html")
        except Exception as e:
            print(f"ERROR {row['sku']}: {e}")
    
    print(f"\nGenerated {count} showcase pages in {SURFACE_ROOT}")

if __name__ == "__main__":
    main()