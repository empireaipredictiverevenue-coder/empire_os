import sqlite3
db = "/root/empire_os/empire_os.db"
c = sqlite3.connect(db)
tables = [r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%prospect%'")]
print("prospect tables:", tables)
for t in tables:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n}")
    except Exception as e:
        print(f"  {t}: err {e}")
# also check si_buyer_outreach + outreach tables
for t in ["si_buyer_outreach", "outreach_prospects", "buyers", "si_buyers"]:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n}")
    except Exception:
        pass
