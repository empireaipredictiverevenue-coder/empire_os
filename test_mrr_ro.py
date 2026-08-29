import sqlite3

DB = "/root/empire_os/empire_os.db"

# Use read-only URI mode
c = sqlite3.connect("file:" + DB + "?mode=ro", uri=True, timeout=30)
c.row_factory = sqlite3.Row

print("leads:", c.execute("SELECT COUNT(*) FROM lane_leads").fetchone())

cur = c.execute("SELECT COUNT(*) FROM si_subscription WHERE status = 'active' AND price_cents > 0")
print("active subs:", cur.fetchone())

cur = c.execute("""
    SELECT plan, billing_cycle, price_cents, COUNT(*) as subs
    FROM si_subscription
    WHERE status = 'active' AND price_cents > 0
    GROUP BY plan, billing_cycle, price_cents
""")
for r in cur.fetchall():
    print(r)

c.close()