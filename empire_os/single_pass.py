#!/usr/bin/env python3
import csv

targets = [
    "plumbing", "hvac", "roofing", "commercial_roofing", "restoration",
    "solar", "solar_installer", "commercial_solar", "managed_it",
    "auto_insurance", "debt_relief", "medical_claims", "hr_staffing",
    "merchant_services", "debt_consolidation", "life_insurance_agent"
]

# Open all output files
file_handles = {}
writers = {}
for t in targets:
    fname = f"/root/empire_os/data_products/{t}_leads.csv"
    fh = open(f"/root/empire_os/data_products/{t}_leads.csv", "w", newline="")
    # We'll create writers after reading header
    file_handles[t] = fh

# Read source and write to targets
with open("/root/empire_os/goldmine_prospects.csv", "r") as fin:
    reader = csv.DictReader(fin)
    fieldnames = [k for k in reader.fieldnames if k is not None]
    
    # Create writers
    for t in targets:
        fh = open(f"/root/empire_os/data_products/{t}_leads.csv", "w", newline="")
        writer = csv.DictWriter(fh, fieldnames=[k for k in reader.fieldnames if k is not None], extrasaction="ignore")
        writer.writeheader()
        file_handles[t] = fh
    
    for row in reader:
        val = row.get("niche", "").strip().lower().replace(" ", "_")
        if val in targets:
            # Re-open correct file and write
            fh = open(f"/root/empire_os/data_products/{val}_leads.csv", "a", newline="")
            writer = csv.DictWriter(fh, fieldnames=[k for k in reader.fieldnames if k is not None], extrasaction="ignore")
            writer.writerow(row)
            fh.close()

print("Done")
