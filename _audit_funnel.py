import sqlite3
c = sqlite3.connect("/root/empire_os/empire_os.db")
tables = ["buyers", "si_buyers", "lanes", "si_charges", "si_invoices", "crm_leads", "lane_leads"]
for t in tables:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        line = f"{t:18} {n}"
        if t == "lanes":
            occ = c.execute("SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''").fetchone()[0]
            line += f"  occupied={occ}"
        print(line)
    except Exception as e:
        print(f"{t:18} ERR {e}")
# funnel: how many leads are in a 'claimed' or past state?
for col in ["status", "state", "stage", "funnel_state"]:
    try:
        rows = c.execute(f"SELECT {col}, COUNT(*) FROM crm_leads GROUP BY {col}").fetchall()
        if rows:
            print(f"\ncrm_leads.{col}:")
            for r in rows[:10]:
                print(f"  {r[0]}: {r[1]}")
            break
    except Exception:
        pass
