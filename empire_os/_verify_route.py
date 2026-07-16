import sqlite3
c = sqlite3.connect("/root/empire_os/empire_os.db")
c.row_factory = sqlite3.Row
print("=== lane_leads total now ===", c.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0])
print("=== lane_leads by category (joined) ===")
for r in c.execute("SELECT l.category, COUNT(*) c FROM lane_leads ll JOIN lanes l ON l.id=ll.lane_id GROUP BY l.category ORDER BY c DESC"):
    print("  %-14s %d" % (r["category"], r["c"]))
print("=== sample newly-routed (non-roofing) pending leads ===")
for r in c.execute("SELECT ll.lane_id, ll.niche, ll.status FROM lane_leads ll JOIN lanes l ON l.id=ll.lane_id WHERE l.category IN ('mass_torts','financial') LIMIT 10"):
    print("  ", r["lane_id"], "|", r["niche"], "|", r["status"])
print("=== pending count overall ===", c.execute("SELECT COUNT(*) FROM lane_leads WHERE status='pending'").fetchone()[0])
