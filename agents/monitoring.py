import json
import time
from empire_os.agents.crawler_agent import get_new_prospects

class SimpleMonitor:
    def __init__(self):
        self.conversion_patterns = {}
        self.seen_prospects = set()
    
    def analyze(self, prospect):
        pid = prospect.get('prospect_id') or hash(str(prospect))
        if pid in self.seen_prospects:
            return
        self.seen_prospects.add(pid)
        
        signals = []
        if prospect.get('email'): signals.append('has_email')
        if prospect.get('score', 0) >= 80: signals.append('high_score')
        if prospect.get('source') in ['goldmine_prospects', 'verified']: signals.append('verified_source')
        
        key = tuple(sorted(signals))
        self.conversion_patterns[key] = self.conversion_patterns.get(key, 0) + 1
        
        if self.conversion_patterns.get(('has_email', 'high_score'), 0) > 5:
            print(f"[MONITOR] High conversion pattern detected - {key}: {self.conversion_patterns[key]}")

# Test monitoring with existing crawler
if __name__ == "__main__":
    monitor = SimpleMonitor()
    
    print("[MONITOR] Starting analysis of new prospects...")
    for metro in ['Houston', 'Dallas-Fort Worth']:
        prospects = get_new_prospects(limit=20, metro=metro)
        for p in prospects:
            monitor.analyze(p)
        print(f"[MONITOR] Analyzed {len(prospects)} prospects from {metro}")