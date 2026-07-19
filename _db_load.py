import csv, sqlite3
db = "/root/empire_os/empire_os.db"
csvp = "/root/empire_os/goldmine_prospects.csv"
c = sqlite3.connect(db)
c.execute("""CREATE TABLE IF NOT EXISTS si_buyer_outreach (
    prospect_id TEXT PRIMARY KEY, business_name TEXT, email TEXT, metro TEXT,
    niche TEXT, phone TEXT, source TEXT, score INTEGER, url TEXT,
    seq_step INTEGER DEFAULT 0, first_touch_at TEXT, last_touch_at TEXT,
    touch_count INTEGER DEFAULT 0, reply_state TEXT DEFAULT 'cold',
    sample_lead_id TEXT, converted INTEGER DEFAULT 0)""")
n = 0
rows = []
with open(csvp) as f:
    for r in csv.DictReader(f):
        n += 1
        rows.append(("gm:" + (r.get("id") or str(n)), r.get("business_name",""), "",
            r.get("metro",""), r.get("niche",""), r.get("phone",""),
            "goldmine_prospects", int(r.get("buy_signal_score") or 0),
            r.get("website",""), "cold"))
        if len(rows) >= 2000:
            c.executemany("INSERT OR IGNORE INTO si_buyer_outreach "
                "(prospect_id,business_name,email,metro,niche,phone,source,score,url,reply_state) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            rows = []
            print("  inserted", n, flush=True)
if rows:
    c.executemany("INSERT OR IGNORE INTO si_buyer_outreach "
        "(prospect_id,business_name,email,metro,niche,phone,source,score,url,reply_state) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
c.commit()
total = c.execute("SELECT COUNT(*) FROM si_buyer_outreach").fetchone()[0]
print("DONE scanned=%d total_now=%d" % (n, total))
