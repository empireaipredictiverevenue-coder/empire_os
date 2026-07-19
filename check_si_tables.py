import sqlite3

conn = sqlite3.connect("/root/empire_os/empire_os.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'si_%'")
for row in c.fetchall():
    print(row[0])
c.execute("SELECT COUNT(*) FROM si_ppc_invoices")
print(f"si_ppc_invoices: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM si_charges")
print(f"si_charges: {c.fetchone()[0]}")