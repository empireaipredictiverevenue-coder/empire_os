#!/usr/bin/env python3
"""Daily trial auto-convert — checks for trials past 7 days, converts to paid."""
import sqlite3, os
from datetime import datetime, timezone, timedelta

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
conn = sqlite3.connect(DB, timeout=30)
now = datetime.now(timezone.utc).isoformat()

# Find trials older than 7 days
trials = conn.execute("""
    SELECT subscription_id, tenant_id, plan, created_at
    FROM si_subscription WHERE status='trial'
""").fetchall()

converted = 0
for sub_id, tenant_id, plan, created_at in trials:
    try:
        if 'T' in created_at:
            dt = datetime.fromisoformat(created_at.replace('Z','+00:00'))
        else:
            dt = datetime.fromisoformat(created_at)
        age = (datetime.now(timezone.utc) - dt).days
        if age >= 7:
            conn.execute("UPDATE si_subscription SET status='active', plan='lane_silver' WHERE subscription_id=?",
                        (sub_id,))
            inv_id = f"inv_autoconv_{sub_id[:12]}"
            conn.execute("""INSERT OR IGNORE INTO si_invoice
                (invoice_id, tenant_id, subscription_id, amount_cents, currency, status, method, description, period_start, period_end, created_at)
                VALUES (?, ?, ?, 9900, 'USD', 'pending', 'crypto_usdt', 'Trial auto-convert $99/mo', ?, ?, ?)""",
                (inv_id, tenant_id, sub_id, created_at, (datetime.now(timezone.utc)+timedelta(days=30)).isoformat(), now))
            converted += 1
    except:
        pass

conn.commit()
conn.close()
print(f"[trial-convert] converted {converted} trials to paid")
