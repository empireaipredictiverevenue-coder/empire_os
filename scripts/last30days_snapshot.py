#!/usr/bin/env python3
"""Empire OS Last 30-Days Revenue Intelligence Snapshot."""
import sqlite3, json, os
from datetime import datetime, timezone

DB = '/root/empire_os/empire_os.db'
conn = sqlite3.connect(DB, timeout=30)

snapshot = {
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'period': 'last_30_days',

    # Active subscriptions by plan (tier)
    'active_subscriptions': conn.execute('''
        SELECT plan, count(*), sum(price_cents)/100.0
        FROM si_subscription WHERE status = 'active'
        GROUP BY plan
    ''').fetchall(),

    # Total MRR by plan (tier)
    'mrr_by_plan': {},

    # Active lanes / seats
    'active_seats': conn.execute('''
        SELECT count(*) FROM lanes WHERE occupied_by IS NOT NULL
    ''').fetchone()[0],

    # Total leads (all lane_leads)
    'total_leads': conn.execute('''
        SELECT count(*) FROM lane_leads
    ''').fetchone()[0],

    # Top 5 plans by lead count from lane_leads buyer_id grouping
    'top_plans': conn.execute('''
        SELECT buyer_id, count(*) as cnt
        FROM lane_leads
        GROUP BY buyer_id
        ORDER BY cnt DESC
        LIMIT 5
    ''').fetchall(),

    # Settlement stats (uses amount_cents, not amount_usdt)
    'settlements': conn.execute('''
        SELECT count(*), sum(amount_cents)/100.0
        FROM si_settlements WHERE settled_at >= date('now', '-30 days')
    ''').fetchone(),
}

# Compute MRR by plan from active_subscriptions data
mrr_data = snapshot['active_subscriptions']
snapshot['mrr_by_plan'] = {
    plan: round(count * (price_cents / 100.0) / count, 2) if count > 0 else 0
    for plan, count, price_cents in mrr_data
}

# Write to feedback
os.makedirs('/root/feedback', exist_ok=True)
with open('/root/feedback/last30days_snapshot.json', 'w') as f:
    json.dump(snapshot, f, indent=2)

print(f'Last 30-days snapshot generated: {snapshot["period"]}')
print(f'Active seats: {snapshot["active_seats"]}')
print(f'Total leads: {snapshot["total_leads"]}')
print(f'Top buyer IDs: {[b[0] for b in snapshot["top_plans"]]}')
print(f'MRR by plan: {snapshot["mrr_by_plan"]}')
print(f'Settlements (30da): {snapshot["settlements"]}')