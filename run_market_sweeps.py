#!/usr/bin/env python3
"""
Run systematic market sweeps across ALL vertical × metro combinations.
Tracks results and builds priority matrix.
"""
import json
import subprocess
import time
import os
from datetime import datetime

# High-value verticals first
VERTICALS = [
    "mass_tort",
    "water_damage",
    "fire_damage",
    "mold_remediation",
    "debt_relief",
    "legal_services",
    "electrical",
    "hvac",
    "plumbing",
    "pest_control",
    "solar",
    "roofing",
    "construction",
    "landscaping"
]

METROS = [
    "phoenix",
    "houston",
    "dallas",
    "austin",
    "san-antonio",
    "chicago",
    "atlanta",
    "miami",
    "denver",
    "los-angeles",
    "new-york",
    "seattle",
    "charlotte",
    "nashville",
    "tampa"
]

# Metro -> State mapping
METRO_STATE = {
    "phoenix": "AZ",
    "houston": "TX",
    "dallas": "TX",
    "austin": "TX",
    "san-antonio": "TX",
    "chicago": "IL",
    "atlanta": "GA",
    "miami": "FL",
    "denver": "CO",
    "los-angeles": "CA",
    "new-york": "NY",
    "seattle": "WA",
    "charlotte": "NC",
    "nashville": "TN",
    "tampa": "FL"
}

# Metro display names
METRO_LABELS = {
    "phoenix": "Phoenix, AZ",
    "houston": "Houston, TX",
    "dallas": "Dallas, TX",
    "austin": "Austin, TX",
    "san-antonio": "San Antonio, TX",
    "chicago": "Chicago, IL",
    "atlanta": "Atlanta, GA",
    "miami": "Miami, FL",
    "denver": "Denver, CO",
    "los-angeles": "Los Angeles, CA",
    "new-york": "New York, NY",
    "seattle": "Seattle, WA",
    "charlotte": "Charlotte, NC",
    "nashville": "Nashville, TN",
    "tampa": "Tampa, FL"
}

RESULTS_FILE = "/root/empire_os/market_sweep_results.json"
SWEEP_SCRIPT = "/root/empire_os/sweeps/market_sweep.py"
DB_PATH = "/root/empire_os/empire_os.db"

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_results(results):
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

def get_leads_count(vertical, metro_slug):
    """Query DB for leads count for vertical/metro combo"""
    metro_label = METRO_LABELS[metro_slug]
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM crm_leads WHERE niche = ? AND metro = ?",
            (vertical, metro_label)
        )
        return cur.fetchone()[0]
    finally:
        conn.close()

def run_sweep(vertical, metro_slug, limit=500):
    """Run market_sweep.py for a vertical/metro combo"""
    metro_label = METRO_LABELS[metro_slug]
    print(f"  Sweeping {vertical} / {metro_label}...")
    try:
        result = subprocess.run(
            ["python3", SWEEP_SCRIPT, "--vertical", vertical, "--metro", metro_slug, "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            # Parse output for inserted count
            output = result.stdout
            for line in output.split('\n'):
                if 'inserted' in line.lower() and 'new leads' in line.lower():
                    # Parse "inserted X/Y" or "done: X new leads"
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.isdigit() and i > 0 and parts[i-1] in ['inserted', 'done:']:
                            return int(p)
            return 0
        else:
            print(f"  Error: {result.stderr[:200]}")
            return -1
    except subprocess.TimeoutExpired:
        print(f"  Timeout!")
        return -1
    except Exception as e:
        print(f"  Error: {e}")
        return -1

def run_batch(batch_num, verticals_batch, limit=300):
    """Run sweeps for a batch of verticals across all metros"""
    results = load_results()
    
    for vertical in verticals_batch:
        print(f"\n=== Batch {batch_num}: Vertical = {vertical} ===")
        for metro_slug in METROS:
            # Check if already swept
            existing = next((r for r in results if r["vertical"] == vertical and r["metro"] == metro_slug), None)
            if existing and existing.get("status") == "swept":
                print(f"  {vertical} / {metro_slug} - already swept ({existing['leads_found']} leads)")
                continue
            
            leads_before = get_leads_count(vertical, metro_slug)
            inserted = run_sweep(vertical, metro_slug, limit)
            leads_after = get_leads_count(vertical, metro_slug)
            leads_found = leads_after - leads_before if inserted >= 0 else 0
            
            pain_score = leads_found if leads_found > 0 else 0
            status = "swept" if inserted >= 0 else "error"
            
            result = {
                "vertical": vertical,
                "metro": metro_slug,
                "state": METRO_STATE[metro_slug],
                "leads_found": leads_found,
                "pain_score": pain_score,
                "status": status
            }
            
            # Update or add result
            if existing:
                existing.update(result)
            else:
                results.append(result)
            
            save_results(results)
            print(f"  {vertical} / {metro_slug}: {leads_found} leads, pain={pain_score}, status={status}")
            
            # Be polite to the API
            time.sleep(2)
    
    return results

def main():
    print("=" * 60)
    print("EMPIRE OS - Systematic Market Sweeps")
    print("=" * 60)
    print(f"Verticals: {len(VERTICALS)}")
    print(f"Metros: {len(METROS)}")
    print(f"Total combos: {len(VERTICALS) * len(METROS)}")
    print(f"Results file: {RESULTS_FILE}")
    
    # Run in batches of 3 verticals to avoid timeouts
    batch_size = 3
    for i in range(0, len(VERTICALS), batch_size):
        batch = VERTICALS[i:i+batch_size]
        batch_num = i // batch_size + 1
        run_batch(batch_num, batch)
        print(f"\nBatch {batch_num} complete. Sleeping 10s...")
        time.sleep(10)
    
    # Print summary
    results = load_results()
    print("\n" + "=" * 60)
    print("SWEEP SUMMARY")
    print("=" * 60)
    
    total_combos = len(VERTICALS) * len(METROS)
    swept = sum(1 for r in results if r["status"] == "swept")
    with_leads = sum(1 for r in results if r["leads_found"] > 0)
    zero_targets = sum(1 for r in results if r["status"] == "swept" and r["leads_found"] == 0)
    total_leads = sum(r["leads_found"] for r in results)
    
    print(f"Total combos: {total_combos}")
    print(f"Swept: {swept}")
    print(f"With leads: {with_leads}")
    print(f"Zero-target (opportunity): {zero_targets}")
    print(f"Total leads found: {total_leads}")
    
    # Top pain verticals
    print("\nTop Pain Verticals (by total leads):")
    vertical_pain = {}
    for r in results:
        if r["status"] == "swept":
            vertical_pain[r["vertical"]] = vertical_pain.get(r["vertical"], 0) + r["leads_found"]
    for v, p in sorted(vertical_pain.items(), key=lambda x: -x[1])[:10]:
        print(f"  {v}: {p} leads")
    
    # Top pain metros
    print("\nTop Pain Metros (by total leads):")
    metro_pain = {}
    for r in results:
        if r["status"] == "swept":
            metro_pain[r["metro"]] = metro_pain.get(r["metro"], 0) + r["leads_found"]
    for m, p in sorted(metro_pain.items(), key=lambda x: -x[1])[:10]:
        print(f"  {m}: {p} leads")
    
    # Zero-target opportunities
    print("\nZero-Target Opportunities (swept, 0 leads = low competition):")
    zero_opps = [r for r in results if r["status"] == "swept" and r["leads_found"] == 0]
    for r in zero_opps[:20]:
        print(f"  {r['vertical']} / {r['metro']} ({r['state']})")

if __name__ == "__main__":
    main()