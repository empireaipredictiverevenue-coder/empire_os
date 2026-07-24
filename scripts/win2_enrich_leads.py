#!/usr/bin/env python3
"""
WIN 2: Enrich Market Sweep Leads — Hunter.io domain search for real emails
Run: python3 /root/empire_os/scripts/win2_enrich_leads.py --batch-size 50
"""

import sys, os, json, sqlite3, time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")
DB = "/root/empire_os/empire_os.db"
ENRICH_LOG = "/root/feedback/enrichment_log.jsonl"

def ensure_enrichment_table():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_enrichment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id TEXT NOT NULL,
            lead_source TEXT NOT NULL,
            domain TEXT,
            email_found TEXT,
            email_confidence INTEGER,
            enrichment_data TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lead_id, lead_source)
        )
    """)
    conn.commit()
    conn.close()

def get_unenriched_leads(limit: int = 50) -> List[Dict]:
    """Get leads from crm_leads that need enrichment"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT c.id, c.company_name, c.domain, c.niche, c.metro, c.source
        FROM crm_leads c
        LEFT JOIN lead_enrichment e ON c.id = e.lead_id AND c.source = e.lead_source
        WHERE (c.email IS NULL OR c.email = '' OR c.email LIKE '%@example.%' OR c.email LIKE '%invalid%')
        AND c.domain IS NOT NULL AND c.domain != ''
        AND e.id IS NULL
        ORDER BY c.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]

def hunter_domain_search(domain: str) -> Optional[Dict]:
    """Call Hunter.io domain-search API"""
    if not HUNTER_API_KEY:
        return None
    
    import requests
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 10},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("data", {})
        else:
            print(f"Hunter API error for {domain}: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Hunter request failed for {domain}: {e}")
    return None

def enrich_lead(lead: Dict) -> Dict:
    """Enrich a single lead with Hunter domain search"""
    domain = lead.get("domain", "").strip()
    if not domain:
        return {"status": "skipped", "reason": "no_domain"}
    
    result = hunter_domain_search(domain)
    if not result:
        return {"status": "failed", "reason": "api_error"}
    
    emails = result.get("emails", [])
    if not emails:
        return {"status": "no_emails", "reason": "domain_found_no_emails"}
    
    # Pick best email (highest confidence, personal not generic)
    best = None
    for e in emails:
        if e.get("type") == "personal" and e.get("confidence", 0) > 50:
            if not best or e["confidence"] > best["confidence"]:
                best = e
    
    if not best:
        # Fallback: any email with confidence
        best = max(emails, key=lambda x: x.get("confidence", 0))
    
    if best and best.get("confidence", 0) >= 30:
        return {
            "status": "enriched",
            "email": best.get("value"),
            "confidence": best.get("confidence"),
            "first_name": best.get("first_name"),
            "last_name": best.get("last_name"),
            "position": best.get("position"),
            "source": "hunter_domain_search"
        }
    
    return {"status": "low_confidence", "reason": f"best_confidence={best.get('confidence', 0) if best else 0}"}

def update_lead_email(lead: Dict, enrichment: Dict):
    """Update crm_leads with found email and log enrichment"""
    conn = sqlite3.connect(DB)
    try:
        # Update crm_leads
        if enrichment.get("email"):
            conn.execute(
                "UPDATE crm_leads SET email = ?, enrichment_score = ?, icp_tier = 'C' WHERE id = ?",
                (enrichment["email"], enrichment["confidence"] / 100.0, lead["id"])
            )
        
        # Log enrichment
        conn.execute("""
            INSERT OR REPLACE INTO lead_enrichment 
            (lead_id, lead_source, domain, email_found, email_confidence, enrichment_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["id"], lead["source"], domain,
            enrichment.get("email"), enrichment.get("confidence"),
            json.dumps(enrichment), enrichment["status"]
        ))
        
        conn.commit()
        
        # Log to feedback
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "lead_enrichment",
            "lead_id": lead["id"],
            "source": lead["source"],
            "domain": domain,
            "result": enrichment
        }
        Path(ENRICH_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(ENRICH_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        return True
    except Exception as e:
        conn.rollback()
        print(f"DB error updating lead {lead['id']}: {e}")
        return False
    finally:
        conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    if not HUNTER_API_KEY:
        print("❌ HUNTER_API_KEY not set in environment")
        sys.exit(1)
    
    ensure_enrichment_table()
    print(f"🔍 Enriching up to {args.batch_size} leads...")
    
    leads = get_unenriched_leads(args.batch_size)
    print(f"Found {len(leads)} unenriched leads with domains")
    
    stats = {"enriched": 0, "skipped": 0, "failed": 0, "no_emails": 0}
    
    for i, lead in enumerate(leads, 1):
        domain = lead.get("domain", "")
        print(f"  [{i}/{len(leads)}] {lead['company_name']} ({domain})")
        
        if args.dry_run:
            print("    DRY RUN - skipping")
            stats["skipped"] += 1
            continue
        
        enrichment = enrich_lead(lead)
        print(f"    → {enrichment['status']}: {enrichment.get('email', enrichment.get('reason', ''))}")
        
        if enrichment["status"] == "enriched":
            if update_lead_email(lead, enrichment):
                stats["enriched"] += 1
            else:
                stats["failed"] += 1
        elif enrichment["status"] == "no_emails":
            stats["no_emails"] += 1
        else:
            stats["skipped"] += 1
        
        time.sleep(0.5)  # Rate limit
    
    print(f"\n=== ENRICHMENT COMPLETE ===")
    print(f"Enriched: {stats['enriched']}")
    print(f"No emails found: {stats['no_emails']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")
    
    # Update warm_prospects view
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE VIEW IF NOT EXISTS warm_prospects AS
        SELECT 
            c.id, c.company_name, c.domain, c.email, c.niche, c.metro,
            c.enrichment_score, c.icp_tier,
            'crm_leads' as source
        FROM crm_leads c
        WHERE c.email IS NOT NULL AND c.email != '' AND c.email NOT LIKE '%@example.%'
        AND c.enrichment_score > 0.3
        ORDER BY c.enrichment_score DESC
    """)
    conn.commit()
    conn.close()
    print("✅ warm_prospects view updated")

if __name__ == "__main__":
    main()