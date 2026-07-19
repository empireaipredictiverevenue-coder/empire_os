import sqlite3
conn = sqlite3.connect("/root/empire_os/empire_os.db")
c = conn.cursor()

# Check failed buyer_delivery details
c.execute("SELECT id, to_email, subject, source, status, created_at, meta_json FROM si_outbox WHERE source='buyer_delivery' AND status='failed' ORDER BY id DESC LIMIT 5")
for row in c.fetchall():
    print(f"ID:{row[0]} to:{row[1]} subj:{row[2][:50]} src:{row[3]} status:{row[4]} created:{row[5]} meta:{row[6][:100]}")

# Check successful deliveries
c.execute("SELECT id, to_email, subject, source, status, created_at FROM si_outbox WHERE status='sent' ORDER BY id DESC LIMIT 3")
for row in c.fetchall():
    print(f"SENT ID:{row[0]} to:{row[1]} subj:{row[2][:50]} src:{row[3]}")

conn.close()