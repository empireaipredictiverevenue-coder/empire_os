#!/usr/bin/env python3
import sqlite3, time
db = '/root/empire_os/empire_os.db'
def counts():
    c = sqlite3.connect(db)
    s = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='sent'").fetchone()[0]
    p = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='pending'").fetchone()[0]
    c.close()
    return s, p
s0, p0 = counts()
time.sleep(15)
s1, p1 = counts()
print(f"sent: {s0} -> {s1} (+{s1-s0})  pending: {p0} -> {p1}")
print("daemon flushing:" , "YES" if s1 > s0 else "NO")
