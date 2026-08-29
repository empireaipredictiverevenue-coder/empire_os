#!/usr/bin/env python3
import gzip, hashlib, os, json
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path("/root/empire_os/data_products")

manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "version": "1.0",
    "note": "Packaged from existing outreach CSVs + goldmine enrichment - 881K leads in DB, these are curated subsets",
    "products": []
}

for csv_file in OUT_DIR.glob("*_leads.csv"):
    if csv_file.stat().st_size == 0:
        continue
    
    # Gzip
    gz_path = csv_file.with_suffix(".csv.gz")
    with open(csv_file, "rb") as f_in:
        with gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
    
    # Hash
    with open(csv_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    
    # Count lines
    lines = sum(1 for _ in open(csv_file)) - 1
    if lines <= 0:
        continue
    
    size_mb = csv_file.stat().st_size / (1024*1024)
    
    niche = csv_file.stem.replace("_leads", "").replace("_", " ")
    
    product = {
        "filename": csv_file.name,
        "gz_filename": gz_path.name,
        "niche": niche,
        "description": f"Enriched {niche} leads",
        "lead_count": lines,
        "price_usd": 499,
        "sha256": sha256,
        "size_mb": round(size_mb, 2),
        "format": "CSV (UTF-8)",
    }
    
    manifest_data = {
        "generated_at": "2026-08-14T22:50:00+00:00",
        "version": "1.0",
        "note": "Packaged from goldmine enrichment + outreach CSVs - 881K leads in DB, these are curated subsets",
        "products": []
    }
    
    # We'll rebuild manifest after loop
    manifest["products"].append(product)
    print(f"{csv_file.name}: {lines} leads, {size_mb:.2f} MB, ${499}")

# Add outreach products
outreach_sources = [
    ("outreach_pack/prospects_2026-07-13.csv", "general_contractor", "NYC permits - general contractors"),
    ("outreach_pack/prospects_2026-07-13.csv", "plumbing", "NYC permits - plumbing"),
    ("outreach_pack/prospects_2026-07-13.csv", "hvac", "NYC permits - HVAC"),
    ("outreach_pack/prospects_2026-07-13.csv", "roofing", "NYC permits - roofing"),
]

import csv
def norm_niche(n):
    return n.strip().lower().replace(" ", "_")

for src_file, niche, desc in [
    ("outreach_pack/prospects_2026-07-13.csv", "general_contractor", "NYC permits - general contractors"),
    ("outreach_pack/prospects_2026-07-13.csv", "plumbing", "NYC permits - plumbing"),
    ("outreach_pack/prospects_2026-07-13.csv", "hvac", "NYC permits - HVAC"),
    ("outreach_pack/prospects_2026-07-13.csv", "roofing", "NYC permits - roofing"),
]:
    src_path = Path("/root/empire_os") / src_file
    dest = Path(f"/root/empire_os/data_products/{niche}_leads_outreach.csv")
    
    def norm_niche(n):
        return n.strip().lower().replace(" ", "_")
    
    target_under = niche.replace(" ", "_")
    target_space = niche.replace("_", " ")
    
    with open(f"/root/empire_os/{src_file}", "r") as fin, open(dest, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        fieldnames = [k for k in reader.fieldnames if k is not None]
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for row in reader:
            val = row.get("niche", "").strip().lower().replace(" ", "_")
            if val == niche:
                writer.writerow(row)
    
    if dest.stat().st_size > 0:
        gz_path = dest.with_suffix(".csv.gz")
        with open(dest, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)
        lines = sum(1 for _ in open(dest)) - 1
        if lines > 0:
            with open(dest, "rb") as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()
            size_mb = dest.stat().st_size / (1024*1024)
            manifest["products"].append({
                "filename": dest.name,
                "gz_filename": gz_path.name,
                "niche": niche,
                "description": f"NYC permits - {niche}",
                "lead_count": lines,
                "price_usd": 499,
                "sha256": sha256,
                "size_mb": round(dest.stat().st_size / (1024*1024), 2),
                "format": "CSV (UTF-8)",
            })
            print(f"{dest.name}: {lines} leads, {size_mb:.2f} MB")

# Write manifest
import hashlib, gzip
manifest = {
    "generated_at": "2026-08-14T23:00:00+00:00",
    "version": "1.0",
    "note": "Packaged from goldmine enrichment + outreach CSVs - 881K leads in DB, these are curated subsets",
    "products": []
}

# Process all CSV files in data_products
for csv_file in Path("/root/empire_os/data_products").glob("*_leads.csv"):
    if csv_file.stat().st_size == 0:
        continue
    lines = sum(1 for _ in open(csv_file)) - 1
    if lines <= 0:
        continue
    
    gz_path = csv_file.with_suffix(".csv.gz")
    with open(csv_file, "rb") as f_in:
        with gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
    
    with open(csv_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    
    lines = sum(1 for _ in open(csv_file)) - 1
    size_mb = csv_file.stat().st_size / (1024*1024)
    niche = csv_file.stem.replace("_leads", "").replace("_", " ")
    
    manifest["products"].append({
        "filename": csv_file.name,
        "gz_filename": gz_path.name,
        "niche": niche,
        "description": f"Enriched {niche} leads" if "outreach" not in csv_file.name else f"NYC permits - {niche}",
        "lead_count": lines,
        "price_usd": 499,
        "sha256": sha256,
        "size_mb": round(size_mb, 2),
        "format": "CSV (UTF-8)",
    })
    print(f"{csv_file.name}: {lines} leads, {size_mb:.2f} MB")

# Write manifest
with open("/root/empire_os/data_products/manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"\nTotal products: {len(manifest['products'])}")
