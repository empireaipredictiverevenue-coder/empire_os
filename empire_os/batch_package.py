#!/usr/bin/env python3
import csv
from pathlib import Path

src_path = Path("/root/empire_os/goldmine_prospects.csv")

def filter_csv(src_path, dest_path, target_niche):
    with open(src_path, "r") as fin, open(dest_path, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        fieldnames = [k for k in reader.fieldnames if k is not None]
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for row in reader:
            val = row.get("niche", "").strip().lower().replace(" ", "_")
            target_under = target_niche.replace(" ", "_")
            target_space = target_niche.replace("_", " ")
            if val == target_under or val == target_space:
                writer.writerow(row)
                count += 1
        return count

niche_list = [
    ("plumbing", "Enriched plumbing leads"),
    ("hvac", "Enriched HVAC leads"),
    ("roofing", "Enriched roofing leads"),
    ("commercial_roofing", "Enriched commercial roofing"),
    ("restoration", "Restoration/water mitigation"),
    ("solar", "Solar leads"),
    ("solar_installer", "Solar installer leads"),
    ("commercial_solar", "Commercial solar leads"),
    ("managed_it", "Managed IT services"),
    ("auto_insurance", "Auto insurance agents"),
    ("debt_relief", "Debt relief services"),
    ("medical_claims", "Medical claims"),
    ("hr_staffing", "HR staffing"),
    ("merchant_services", "Merchant services"),
    ("debt_consolidation", "Debt consolidation"),
    ("life_insurance_agent", "Life insurance agents"),
]

src_path = Path("/root/empire_os/goldmine_prospects.csv")
dest_dir = Path("/root/empire_os/data_products")

for niche_key, desc in niche_list:
    dest = dest_dir / f"{niche_key}_leads.csv"
    with open(src_path, "r") as fin, open(dest, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        fieldnames = [k for k in reader.fieldnames if k is not None]
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for row in reader:
            val = row.get("niche", "").strip().lower().replace(" ", "_")
            if val == niche_key:
                writer.writerow(row)
                count += 1
    
    if count == 0:
        print(f"SKIP {niche_key}: 0 leads")
    else:
        print(f"{niche_key}: {count} leads")
