import sqlite3

DB = "/root/empire_os/empire_os.db"
c = sqlite3.connect(DB, timeout=30, isolation_level=None)
c.row_factory = sqlite3.Row

print("Testing si_subscription queries...")

cur = c.execute("SELECT COUNT(*) FROM si_subscription WHERE status = 'active' AND price_cents > 0")
print('active subs:', cur.fetchone())

cur = c.execute("SELECT plan, billing_cycle, price_cents, COUNT(*) as subs FROM si_subscription WHERE status = 'active' AND price_cents > 0 GROUP BY plan, billing_cycle, price_cents")
for r in cur.fetchall():
    print(r)