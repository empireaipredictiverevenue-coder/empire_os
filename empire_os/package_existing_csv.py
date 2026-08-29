#!/usr/bin/env python3
"""Package existing CSV files as data products for buyers ($499 each)."""
import os, sys, csv, json, gzip, hashlib, shutil
from datetime import datetime, timezone
from pathlib import Path

SRC_DIR = Path("/root/empire_os")
OUT_DIR = Path("/root/empire_os/data_products")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Normalize niche names
def norm_niche(n):
    return n.strip().lower().replace(" ", "_")

def filter_csv(src_path, dest_path, target_niche):
    """Filter CSV to only rows matching niche (handles both space and underscore formats)."""
    # Target can match either format
    target_space = target_niche.strip().lower().replace("_", " ")
    target_under = target_niche.strip().lower().replace(" ", "_")
    
    with open(src_path, "r") as fin, open(dest_path, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        fieldnames = [k for k in reader.fieldnames if k is not None]
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for row in reader:
            val = norm_niche(row.get("niche", ""))
            if val == target_under or val == target_space:
                writer.writerow(row)
                count += 1
        return count

def package_file(src_filename, dest_filename, niche, desc):
    """Package a CSV (either full or filtered)."""
    src = SRC_DIR / src_filename
    if not src.exists():
        print(f"SKIP: {src} not found")
        return None
    
    dest = OUT_DIR / dest_filename
    
    if "goldmine" in src_filename and niche != "mixed_b2b":
        count = filter_csv(src, dest, niche)
    else:
        import shutil
        shutil.copy2(src, dest)
        with open(dest, "r") as f:
            count = sum(1 for _ in f) - 1  # minus header
    
    if count == 0:
        print(f"SKIP: {dest_filename} - 0 leads for {niche}")
        if dest.exists():
            dest.unlink()
        return None
    
    # Gzip
    gz_path = dest.with_suffix(".csv.gz")
    with open(dest, "rb") as f_in:
        with gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
    
    # Hash
    with open(dest, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    
    size_mb = dest.stat().st_size / (1024*1024)
    
    product = {
        "filename": dest_filename,
        "gz_filename": gz_path.name,
        "niche": niche,
        "description": desc,
        "lead_count": count,
        "price_usd": 499,
        "sha256": sha256,
        "size_mb": round(size_mb, 2),
        "format": "CSV (UTF-8)",
    }
    print(f"Packaged: {dest_filename} ({count} leads, {product['size_mb']} MB) - ${product['price_usd']}")
    return product

def main():
    import hashlib
    from datetime import datetime, timezone
    
    SRC_DIR = Path("/root/empire_os")
    OUT_DIR = Path("/root/empire_os/data_products")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "note": "Packaged from existing outreach CSVs + goldmine enrichment - 881K leads in DB, these are curated subsets",
        "products": []
    }
    
    # Goldmine products (filtered by niche - exact match from goldmine)
    goldmine_niches = [
        ("general_contractor_leads.csv", "general contractor", "Enriched general contractors"),
        ("general_contractor_underscore_leads.csv", "general_contractor", "Enriched general contractors (alt format)"),
        ("plumbing_leads.csv", "plumbing", "Enriched plumbing leads"),
        ("hvac_leads.csv", "hvac", "Enriched HVAC leads"),
        ("roofing_leads.csv", "roofing", "Enriched roofing leads"),
        ("commercial_roofing_leads.csv", "commercial roofing", "Enriched commercial roofing"),
        ("commercial_roofing_underscore_leads.csv", "commercial_roofing", "Enriched commercial roofing (alt)"),
        ("restoration_leads.csv", "restoration", "Restoration/water mitigation"),
        ("solar_leads.csv", "solar", "Solar leads"),
        ("solar_installer_leads.csv", "solar installer", "Solar installer leads"),
        ("commercial_solar_leads.csv", "commercial solar", "Commercial solar leads"),
        ("managed_it_leads.csv", "managed it", "Managed IT services"),
        ("auto_insurance_leads.csv", "auto insurance", "Auto insurance agents"),
        ("debt_relief_leads.csv", "debt relief", "Debt relief services"),
        ("medical_claims_leads.csv", "medical claims", "Medical claims"),
        ("hr_staffing_leads.csv", "hr staffing", "HR staffing"),
        ("merchant_services_leads.csv", "merchant services", "Merchant services"),
        ("debt_consolidation_leads.csv", "debt consolidation", "Debt consolidation"),
        ("life_insurance_agent_leads.csv", "life insurance agent", "Life insurance agents"),
        ("solar_installer_leads.csv", "solar installer", "Solar installer leads"),
    ]
    
    for filename, niche, desc in goldmine_niches:
        p = package_file("goldmine_prospects.csv", filename, niche, desc)
        if p: manifest["products"].append(p)
    
    # Outreach products (NYC permits)
    outreach_niches = [
        ("general_contractor_leads_outreach.csv", "general_contractor", "NYC permits - general contractors"),
        ("plumbing_leads_outreach.csv", "plumbing", "NYC permits - plumbing"),
        ("hvac_leads_outreach.csv", "hvac", "NYC permits - HVAC"),
        ("roofing_leads_outreach.csv", "roofing", "NYC permits - roofing"),
    ]
    
    for filename, niche, desc in outreach_niches:
        p = package_file("outreach_pack/prospects_2026-07-13.csv", filename, niche, desc)
        if p: manifest["products"].append(p)
    
    # Goldmine full (mixed B2B)
    p = package_file("goldmine_prospects.csv", "goldmine_b2b_enriched.csv", "mixed_b2b", "Full enriched B2B prospects (all niches)")
    if p: manifest["products"].append(p)
    
    # Write manifest
    manifest_path = OUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nManifest: {manifest_path}")
    print(f"Products: {len(manifest['products'])}")
    for prod in manifest["products"]:
        print(f"  {prod['filename']}: {prod['lead_count']} leads - ${prod['price_usd']}")

if __name__ == "__main__":
    import json
    from datetime import datetime, timezone
    main()
