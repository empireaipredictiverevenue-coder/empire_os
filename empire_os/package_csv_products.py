#!/usr/bin/env python3
"""Package CSV datasets for sale to lead buyers ($499 each)."""
import os, sys, sqlite3, csv, json, gzip, hashlib
from datetime import datetime, timezone
from pathlib import Path

DB = "/root/empire_os/empire_os.db"
OUT_DIR = Path("/root/empire_os/data_products")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Get niches from DB ordered by volume (descending)
conn = sqlite3.connect(DB)
cursor = conn.execute("""
    SELECT niche, COUNT(*) as cnt 
    FROM lane_leads 
    WHERE status = 'pending' AND niche != '' 
    GROUP BY niche 
    ORDER BY cnt DESC
""")
niches = [(row[0], row[1]) for row in cursor.fetchall()]
conn.close()

print(f"Found {len(niches)} niches with pending leads")

# Product list using exact niche values from DB, ordered by volume
PRODUCTS = []

# Add individual niche products (top 20 by volume)
for niche, count in niches[:20]:
    safe_name = niche.replace(" ", "_").replace("/", "_").lower()
    PRODUCTS.append((f"{safe_name}_leads.csv", niche, "All metros"))

# Master dataset
PRODUCTS.append(("all_niches_all_metros.csv", None, "All metros"))

def export_csv(niche_filter=None, metros="All", output_path=None):
    """Export leads to CSV with filtering."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    
    where = "WHERE status = ?"
    params = ["pending"]
    
    if niche_filter:
        where += " AND niche = ?"
        params.append(niche_filter)
    
    if metros != "All":
        where += " AND metro = ?"
        params.append(metros)
    
    sql = f"""
        SELECT id, lane_id, prospect_id, status, omega_score, omega_tier,
               niche, sub_niche, metro, city, state, zip, street,
               icp_fit_score, icp_tier, buyer_id, payout_usd, predicted_value_usd,
               buyer_count, value_enriched_at, cortex_score, aeo_priority, lease_id
        FROM lane_leads
        {where}
        ORDER BY omega_score DESC
    """
    
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    
    if not output_path:
        output_path = OUT_DIR / f"leads_{niche_filter or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    with open(output_path, 'w', newline='') as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
    
    print(f"Exported {len(rows)} leads to {output_path}")
    return len(rows), output_path

def package_all():
    """Generate all CSV products."""
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "products": []
    }
    
    for filename, niche, metros in PRODUCTS:
        path = OUT_DIR / filename
        count, _ = export_csv(niche_filter=niche, metros=metros, output_path=path)
        
        # Create gzipped version
        gz_path = path.with_suffix('.csv.gz')
        with open(path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Calculate hash
        with open(path, 'rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()
        
        product_info = {
            "filename": filename,
            "gz_filename": gz_path.name,
            "niche": niche,
            "metros": metros,
            "lead_count": count,
            "price_usd": 499,
            "sha256": sha256,
            "format": "CSV (UTF-8)",
            "fields": [
                "id", "lane_id", "prospect_id", "status", "omega_score", "omega_tier",
                "niche", "sub_niche", "metro", "city", "state", "zip", "street",
                "icp_fit_score", "icp_tier", "buyer_id", "payout_usd", "predicted_value_usd",
                "buyer_count", "value_enriched_at", "cortex_score", "aeo_priority", "lease_id"
            ]
        }
        manifest["products"].append(product_info)
        print(f"Packaged: {filename} ({count} leads)")
    
    # Write manifest
    manifest_path = OUT_DIR / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nManifest written to {manifest_path}")
    print(f"Total products: {len(manifest['products'])}")
    return manifest

if __name__ == "__main__":
    import hashlib
    from datetime import datetime, timezone
    manifest = package_all()
    print("\n=== DATA PRODUCTS READY FOR SALE ===")
    for p in manifest["products"]:
        print(f"  {p['filename']}: {p['lead_count']} leads - ${p['price_usd']}")
