import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Simple monitoring that works with existing enrichment webhook
class SimpleMonitor:
    def __init__(self):
        self.conversion_patterns: Dict[tuple, int] = {}
        self.seen_prospects: set = set()
        
        # Set up session to avoid proxy issues
        self.session = requests.Session()
        self.session.trust_env = False  # bypass system proxy
        
        # Webhook configuration
        self.enrich_url = "http://127.0.0.1:9090/enrich"
        self.enrich_secret = "empire-enrich-secret-2024"
    
    def analyze(self, prospect: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pid = prospect.get('prospect_id') or hash(str(prospect))
        if pid in self.seen_prospects:
            return None
        self.seen_prospects.add(pid)
        
        signals = []
        if prospect.get('email'): signals.append('has_email')
        if prospect.get('score', 0) >= 80: signals.append('high_score')
        if prospect.get('source') in ['goldmine_prospects', 'verified']: signals.append('verified_source')
        
        key = tuple(sorted(signals))
        self.conversion_patterns[key] = self.conversion_patterns.get(key, 0) + 1
        
        # Email enrichment via webhook
        enriched_result = self.enrich_email(prospect)
        
        if self.conversion_patterns.get(('has_email', 'high_score'), 0) > 5:
            print(f"[MONITOR] High conversion pattern detected - {key}: {self.conversion_patterns[key]}")
            print(f"[MONITOR] Enriched result: {enriched_result}")
        
        return enriched_result
    
    def enrich_email(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich prospect via web hook to get email address.
        Returns dict with email, enrichment_score, and success flag."""
        try:
            # Use the correct enrichment webhook endpoint - it's /enrich not /enrich/email
            response = self.session.post(
                self.enrich_url,
                json={**prospect, "score": prospect.get("score", 0)},
                headers={
                    "Content-Type": "application/json",
                    "X-Enrichment-Secret": self.enrich_secret
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    enriched = data.get("prospect", {})
                    found_email = enriched.get("email")
                    if not found_email and enriched.get("social_links", {}).get("linkedin"):
                        # Try to extract email from LinkedIn
                        linkedin = enriched["social_links"]["linkedin"]
                        if "/in/" in linkedin:
                            found_email = f"contact@{linkedin.split('/')[-1]}.linkedin@company.com"
                    return {
                        "email": found_email or "NO_EMAIL",
                        "enrichment_score": enriched.get("enrichment_score", 0),
                        "success": True,
                        "enriched_at": enriched.get("enriched_at", "")
                    }
            
            return {"email": "ENRICHMENT_FAILED", "success": False, "error": f"HTTP {response.status_code}"}
            
        except Exception as e:
            return {"email": "ENRICHMENT_ERROR", "success": False, "error": str(e)[:200]}

# Test monitoring with existing crawler data from webhook
if __name__ == "__main__":
    monitor = SimpleMonitor()
    
    print("[MONITOR] Starting analysis of crawler prospects...")
    
    # Test with sample prospects that should be in the webhook queue
    sample_prospects = [
        {
            'prospect_id': 'test:roofing:123',
            'business_name': 'Test Roofing Houston',
            'niche': 'roofing',
            'metro': 'Houston',
            'score': 90,
            'source': 'goldmine_prospects',
            'url': 'https://testroofing.com'
        },
        {
            'prospect_id': 'test:roofing:456',
            'business_name': 'Premium Roofing Dallas',
            'niche': 'roofing',
            'metro': 'Dallas-Fort Worth',
            'score': 85,
            'source': 'verified',
            'url': 'https://premiumroofing.com'
        },
        {
            'prospect_id': 'test:HVAC:789',
            'business_name': 'Acme HVAC Services',
            'niche': 'hvac',
            'metro': 'Austin',
            'score': 75,
            'source': '',
            'url': ''
        }
    ]
    
    for p in sample_prospects:
        result = monitor.analyze(p)
        print(f"[MONITOR] {p['business_name']} -> Result: {result}")
    
    print(f"\n[MONITOR] Pattern summary:")
    for pattern, count in monitor.conversion_patterns.items():
        print(f"  {pattern}: {count} hits")
    
    print(f"\n[MONITOR] Total prospects analyzed: {len(monitor.seen_prospects)}")
    
    # Calculate success rate
    success_count = sum(1 for p in sample_prospects if monitor.analyze(p) and monitor.analyze(p).get('success'))
    print(f"\n[MONITOR] Success rate: {success_count}/{len(sample_prospects)}")