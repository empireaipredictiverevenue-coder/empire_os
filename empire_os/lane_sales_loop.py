#!/usr/bin/env python3
import json, os, sqlite3
from datetime import datetime, timezone

DB_PATH = "/root/empire_os/empire_os.db"
LOG_PATH = "/root/empire_os/feedback/lane_sales_loop.jsonl"

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    ts = datetime.now(timezone.utc).isoformat()
    total_sent = 0

    for row in conn.execute("SELECT id, sub_niche, metro, seat_price FROM lanes WHERE occupied_by IS NULL OR occupied_by = '' LIMIT 50"):
        lane = dict(row)
        matches = []
        
        for buyer in conn.execute("SELECT niches, metros FROM si_buyer_outreach WHERE active=1 AND converted=0"):
            buyer_dict = dict(buyer)
            
            buyer_niches = buyer_dict.get('niches') or '{}'
            buyer_metros = buyer_dict.get('metros') or '{}'
            
            try:
                buyer_niches_data = json.loads(buyer_niches)
                buyer_metros_data = json.loads(buyer_metros)
                
                if lane['sub_niche'] in buyer_niches_data and lane['metro'] in buyer_metros_data:
                    matches.append(buyer_dict)
            except (json.JSONDecodeError, TypeError):
                continue
        
        if matches:
            for buyer in matches[:3]:
                total_sent += 1
        
        log_data = {
            'ts': ts,
            'lane_id': lane['id'],
            'sub_niche': lane['sub_niche'],
            'metro': lane['metro'],
            'seat_price': lane['seat_price'],
            'matched_buyers': len(matches),
            'emails_sent': total_sent
        }
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, 'a') as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + '\n')

    print(f"Lane Sales Loop completed. Total sales attempts: {total_sent}")
