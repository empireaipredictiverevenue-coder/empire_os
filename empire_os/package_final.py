#!/usr/bin/env python3
import csv, gzip, hashlib, shutil, json
from datetime import datetime, timezone
from pathlib import Path

SRC_DIR = Path("/root/empire_os")
OUT_DIR = Path("/root/empire_os/data_products")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def norm_niche(n):
    return n.strip().lower().replace(" ", "_")

def filter_csv(src_path, dest_path, target_niche):
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

products = [
    ("goldmine_prospects.csv", "general_contractor_leads.csv", "general contractor", "Enriched general contractors"),
    ("goldmine_prospects.csv", "plumbing_leads.csv", "plumbing", "Enriched plumbing leads"),
    ("goldmine_prospects.csv", "hvac_leads.csv", "hvac", "Enriched HVAC leads"),
    ("goldmine_prospects.csv", "roofing_leads.csv", "roofing", "Enriched roofing leads"),
    ("goldmine_prospects.csv", "commercial_roofing_leads.csv", "commercial roofing", "Enriched commercial roofing"),
    ("goldmine_prospects.csv", "restoration_leads.csv", "restoration", "Restoration/water mitigation"),
    ("goldmine_prospects.csv", "solar_leads.csv", "solar", "Solar leads"),
    ("goldmine_prospects.csv", "solar_installer_leads.csv", "solar installer", "Solar installer leads"),
    ("goldmine_prospects.csv", "commercial_solar_leads.csv", "commercial solar", "Commercial solar leads"),
    ("goldmine_prospects.csv", "managed_it_leads.csv", "managed it", "Managed IT services"),
    ("goldmine_prospects.csv", "auto_insurance_leads.csv", "auto insurance", "Auto insurance agents"),
    ("goldmine_prospects.csv", "debt_relief_leads.csv", "debt relief", "Debt relief services"),
    ("goldmine_prospects.csv", "medical_claims_leads.csv", "medical claims", "Medical claims"),
    ("goldmine_prospects.csv", "hr_staffing_leads.csv", "hr staffing", "HR staffing"),
    ("goldmine_prospects.csv", "merchant_services_leads.csv", "merchant services", "Merchant services"),
    ("goldmine_prospects.csv", "debt_consolidation_leads.csv", "debt consolidation", "Debt consolidation"),
    ("goldmine_prospects.csv", "life_insurance_agent_leads.csv", "life insurance agent", "Life insurance agents"),
    ("outreach_pack/prospects_2026-07-13.csv", "general_contractor_leads_outreach.csv", "general_contractor", "NYC permits - general contractors"),
    ("outreach_pack/prospects_2026-07-13.csv", "plumbing_leads_outreach.csv", "plumbing", "NYC permits - plumbing"),
    ("outreach_pack/prospects_2026-07-13.csv", "hvac_leads_outreach.csv", "hvac", "NYC permits - HVAC"),
    ("outreach_pack/prospects_2026-07-13.csv", "roofing_leads_outreach.csv", "roofing", "NYC permits - roofing"),
]

OUT_DIR = Path("/root/empire_os/data_products")
OUT_DIR.mkdir(parents=True, exist_ok=True)

manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "version": "1.0",
    "note": "Packaged from existing outreach CSVs + goldmine enrichment - 881K leads in DB, these are curated subsets",
    "products": []
}

for src, dest, niche, desc in products:
    src_path = Path("/root/empire_os") / src
    dest_path = OUT_DIR / dest
    
    if not src_path.exists():
        print(f"SKIP: {src} not found")
        continue
    
    if "goldmine" in src:
        count = filter_csv(src_path, dest_path, niche)
    else:
        shutil.copy2(src_path, dest_path)
        with open(dest_path, "r") as f:
            count = sum(1 for _ in f) - 1
    
    if count == 0:
        print(f"SKIP: {dest} - 0 leads for {niche}")
        if dest_path.exists():
            dest_path.unlink()
        continue
    
    gz_path = dest_path.with_suffix(".csv.gz")
    with open(dest_path, "rb") as f_in:
        with gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
    
    with open(dest_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    
    size_mb = dest_path.stat().st_size / (1024*1024)
    
    manifest["products"].append({
        "filename": dest_path.name,
        "gz_filename": gz_path.name,
        "niche": niche,
        "description": desc,
        "lead_count": count,
        "price_usd": 499,
        "sha256": sha256,
        "size_mb": round(size_mb, 2),
        "format": "CSV (UTF-8)",
    })
    print(f"Packaged: {dest} ({count} leads) - $499")

# Write manifest
manifest_data = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "version": "1.0",
    "note": "Packaged from existing outreach CSVs + goldmine enrichment - 881K leads in DB, these are curated subsets",
    "products": manifest["products"]
}
with open(OUT_DIR / "manifest.json", "w") as f:
    json.dump(manifest_data, f, indent=2)

print(f"\nTotal products: {len(manifest['products'])}")
for p in manifest["products"]:
    print(f"  {p['filename']}: {p['lead_count']} leads - ${p['price_usd']}")

if __name__ == "__main__":
    import csv, gzip, hashlib, shutil, json
    from datetime import datetime, timezone
    from pathlib import Path

    def norm_niche(n):
        return n.strip().lower().replace(" ", "_")

    def filter_csv(src_path, dest_path, target_niche):
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

    # Run packaging
    manifest = {"products": []}
    for src, dest, niche, desc in products:
        src_path = Path("/root/empire_os") / src
        dest_path = OUT_DIR / dest
        
        if not src_path.exists():
            print(f"SKIP: {src} not found")
            continue
        
        if "goldmine" in src:
            count = filter_csv(src_path, dest_path, niche)
        else:
            shutil.copy2(src_path, dest_path)
            with open(dest_path, "r") as f:
                count = sum(1 for _ in f) - 1
        
        if count == 0:
            print(f"SKIP: {dest} - 0 leads for {niche}")
            if dest_path.exists():
                dest_path.unlink()
            continue
        
        gz_path = dest_path.with_suffix(".csv.gz")
        with open(dest_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)
        
        with open(dest_path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()
        
        size_mb = dest_path.stat().st_size / (1024*1024)
        
        manifest["products"].append({
            "filename": dest_path.name,
            "gz_filename": gz_path.name,
            "niche": niche,
            "description": desc,
            "lead_count": count,
            "price_usd": 499,
            "sha256": sha256,
            "size_mb": round(size_mb, 2),
            "format": "CSV (UTF-8)",
        })
        print(f"Packaged: {dest} ({count} leads) - $499")

    manifest_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "note": "Packaged from existing outreach CSVs + goldmine enrichment - 881K leads in DB, these are curated subsets",
        "products": manifest["products"]
    }
    with open(OUT_DIR / "manifest.json", "w") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"\nTotal products: {len(manifest['products'])}")
    for p in manifest["products"]:
        print(f"  {p['filename']}: {p['lead_count']} leads - ${p['price_usd']}")

