import sqlite3
db=sqlite3.connect("/root/empire_os/empire.db")
cur=db.cursor()
print("--- tables matching outreach/prospect/lead ---")
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%outreach%' OR name LIKE '%prospect%' OR name LIKE '%lead%')"):
    print(r[0])
print("--- find db with b2b_int_gm ---")
for db_path in ["/root/empire_os/empire.db"]:
    db=sqlite3.connect(db_path)
    cur=db.cursor()
    tbls = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tbls:
        try:
            cnt = cur.execute(f'SELECT COUNT(*) FROM "{t}" WHERE prospect_id LIKE "b2b_int_gm:%%"').fetchone()[0]
            if cnt > 0:
                print(f"  DB={db_path} TABLE={t} count={cnt}")
                for r in cur.execute(f'SELECT prospect_id, email, url, business_name FROM "{t}" WHERE prospect_id LIKE "b2b_int_gm:%%" LIMIT 3'):
                    print("   ", r)
        except Exception as e:
            pass