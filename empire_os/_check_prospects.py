import sqlite3
c = sqlite3.connect("/root/empire_os/empire_os.db")
c.row_factory = sqlite3.Row
# Find any mass_tort-style prospect niches in the table
print("=== prospect niches that SHOULD map to mass_torts ===")
for r in c.execute("SELECT niche, COUNT(*) c FROM si_buyer_outreach WHERE lower(niche) LIKE '%class action%' OR lower(niche) LIKE '%mass tort%' OR lower(niche) LIKE '%personal injury%' GROUP BY niche"):
    print("  ", repr(r["niche"]), r["c"])
print("=== consumers of financial/mass_tort-targeted niches present ===")
for kw in ("debt", "insurance", "mortgage", "addiction", "medical"):
    n = c.execute("SELECT COUNT(*) FROM si_buyer_outreach WHERE lower(niche) LIKE ?", ("%" + kw + "%",)).fetchone()[0]
    print("  %-12s %d" % (kw, n))
