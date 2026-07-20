#!/usr/bin/env python3
"""Rewrite 127.0.0.1:8000 -> 10.118.155.218:8081 in si_outbox.meta_json.webhook."""
import sqlite3, json, sys

DB = "/root/empire_os/empire_os.db"
OLD = "http://127.0.0.1:8000"
NEW = "http://10.118.155.218:8081"

c = sqlite3.connect(DB, timeout=60)
c.execute("PRAGMA busy_timeout=60000")
pre = c.execute("SELECT COUNT(*) FROM si_outbox WHERE meta_json LIKE ?", ("%127.0.0.1:8000%",)).fetchone()[0]
print(f"PRE rows with dead URL: {pre}")

fixed = 0
samples = []
rows = c.execute("SELECT id, meta_json FROM si_outbox WHERE meta_json LIKE ?", ("%127.0.0.1:8000%",)).fetchall()
for id_, meta in rows:
    if not meta:
        continue
    try:
        d = json.loads(meta)
    except Exception:
        continue
    changed = False
    for k in list(d.keys()):
        v = d[k]
        if isinstance(v, str) and OLD in v:
            d[k] = v.replace(OLD, NEW)
            changed = True
    if changed:
        new_meta = json.dumps(d)
        c.execute("UPDATE si_outbox SET meta_json=? WHERE id=?", (new_meta, id_))
        fixed += 1
        if len(samples) < 3:
            samples.append((id_, new_meta))

c.commit()

post = c.execute("SELECT COUNT(*) FROM si_outbox WHERE meta_json LIKE ?", ("%127.0.0.1:8000%",)).fetchone()[0]
print(f"POST rows with dead URL: {post}")
print(f"FIXED rows: {fixed}")
for s in samples:
    print(f"  sample id={s[0]} meta={s[1]}")
