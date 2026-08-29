import json
import sqlite3
import sys
import os
from datetime import datetime, date, timezone

DB = '/root/empire_os/empire_os.db'

def new_conn():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute('PRAGMA busy_timeout=5000')
    c.execute('PRAGMA read_uncommitted=1')
    c.row_factory = sqlite3.Row
    return c

def scalar(sql):
    c = new_conn()
    try:
        cur = c.execute(sql)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        c.close()

def rows(sql):
    c = new_conn()
    try:
        cur = c.execute(sql)
        return [dict(r) for r in cur.fetchall()]
    finally:
        c.close()

# Test each section individually
print('Testing leads...')
RS = {}
RS['leads'] = {
    'total': scalar('SELECT COUNT(*) FROM lane_leads'),
    'last_24h': scalar("SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now','-1 day') LIMIT 1000"),
    'by_tier': {r['omega_tier']: r['cnt'] for r in rows("SELECT omega_tier, COUNT(*) as cnt FROM lane_leads GROUP BY omega_tier LIMIT 20") if r['omega_tier']},
    'avg_fit_score': scalar("SELECT ROUND(AVG(MIN(100, MAX(0, icp_fit_score))), 1) FROM lane_leads WHERE icp_fit_score IS NOT NULL LIMIT 5000") or 0,
}
print('leads done')

print('Testing a2a...')
RS['a2a'] = {
    'total': scalar('SELECT COUNT(*) FROM buyer_leads LIMIT 1000'),
    'delivered_http_200': scalar("SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000"),
    'locked_usd': scalar("SELECT ROUND(SUM(payout_usd), 2) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000") or 0,
}
print('a2a done')

print('Testing buyers...')
RS['buyers'] = {
    'total': scalar('SELECT COUNT(*) FROM si_buyer_outreach LIMIT 1000'),
    'priced': scalar("SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0 LIMIT 1000"),
    'with_endpoint': scalar("SELECT COUNT(*) FROM si_buyer_outreach WHERE endpoint_url != '' AND endpoint_url IS NOT NULL LIMIT 1000"),
}
print('buyers done')

print('Testing charges...')
RS['charges'] = {
    'total': scalar('SELECT COUNT(*) FROM si_charges LIMIT 1000'),
    'open': scalar("SELECT COUNT(*) FROM si_charges WHERE status='open' LIMIT 1000"),
    'paid': scalar("SELECT COUNT(*) FROM si_charges WHERE status='paid' LIMIT 1000"),
    'vault_usdc': scalar("SELECT ROUND(COALESCE(SUM(amount_cents), 0) / 100.0, 4) FROM si_charges WHERE status='paid' LIMIT 1000") or 0,
}
print('charges done')

print('Testing settlements...')
RS['settlements'] = {'rows': scalar('SELECT COUNT(*) FROM si_settlements LIMIT 1000')}
print('settlements done')

print('Testing MRR...')
mrr_rows = rows('''
    SELECT plan, billing_cycle, price_cents, COUNT(*) as subs
    FROM si_subscription
    WHERE status = 'active' AND price_cents > 0
    GROUP BY plan, billing_cycle, price_cents LIMIT 1000
''')
by_plan = {}
total_cents = 0
total_subs = 0
for r in mrr_rows:
    if r['billing_cycle'] == 'annual':
        monthly = r['price_cents'] / 12.0
    else:
        monthly = r['price_cents']
    monthly_cents = int(monthly)
    by_plan[r['plan']] = by_plan.get(r['plan'], 0) + monthly_cents * r['subs']
    total_cents += monthly_cents * r['subs']
    total_subs += r['subs']
RS['mrr'] = {
    'total_usd': round(total_cents / 100.0, 2),
    'total_subs': total_subs,
    'by_plan': {k: round(v / 100.0, 2) for k, v in by_plan.items()},
}
RS['arr'] = RS['mrr']['total_usd'] * 12
print('MRR done')

print(json.dumps(RS, default=str))