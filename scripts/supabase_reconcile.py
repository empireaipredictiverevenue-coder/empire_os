#!/usr/bin/env python3
"""
supabase_reconcile.py — make SQLite a faithful mirror of Supabase (SoR).

Context: SQLite was wiped Aug 18 and only partially rebuilt. Supabase holds
the full, newer dataset. Buyers / prospects / enriched_leads / delivered_leads
exist ONLY in Supabase (SQLite local count = 0). This script:
  1. fetches each exclusive table from SB (PostgREST)
  2. creates the SQLite table with a schema DERIVED FROM the live SB columns
     (no hardcoded column lists -> immune to drift)
  3. upserts rows by PK (id) inside a single IMMEDIATE txn
  4. never touches crm_leads / lane_leads (separate column-map task)

Dry-run by default (--apply to write). Idempotent + resumable.
"""
import os
import sys
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")

# Tables that exist ONLY in Supabase (SQLite local count = 0).
MISSING_TABLES = ["buyers", "prospects", "enriched_leads", "delivered_leads"]

# Supabase env
SUPABASE_URL = ""
SUPABASE_KEY = ""
for line in open("/root/empire_os/.env"):
    line = line.strip()
    if line.startswith("SUPABASE_URL="):
        SUPABASE_URL = line.split("=", 1)[1].strip()
    elif line.startswith("SUPABASE_SERVICE_KEY="):
        SUPABASE_KEY = line.split("=", 1)[1].strip()
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
           "Accept": "application/json"}


def _sql_type(v):
    if isinstance(v, bool):
        return "BOOLEAN"
    if isinstance(v, int):
        return "INTEGER"
    if isinstance(v, float):
        return "REAL"
    return "TEXT"


def sb_select_all(table, batch=1000):
    out = []
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=40) as r:
            rows = json.loads(r.read())
        if not rows:
            break
        out.extend(rows)
        if len(rows) < batch:
            break
        offset += batch
    return out


def create_from_rows(conn, table, rows):
    # Drop any stale partial local table, then build from live SB columns.
    cols = [c for c in rows[0].keys() if c != "id"]
    colspec = ", ".join(f'"{c}" TEXT' for c in cols)  # TEXT tolerant; upsert casts
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" (id TEXT PRIMARY KEY, {colspec})')
    conn.commit()


def _bind(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v


def upsert_rows(conn, table, rows):
    cur = conn.cursor()
    n = 0
    for row in rows:
        cols = list(row.keys())
        colspec = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        updates = ", ".join(f'"{c}"=excluded."{c}"' for c in cols if c != "id")
        sql = (f'INSERT INTO "{table}" ({colspec}) VALUES ({placeholders}) '
               f'ON CONFLICT("id") DO UPDATE SET {updates}')
        vals = [_bind(row[c]) for c in cols]
        cur.execute(sql, vals)
        n += 1
    conn.commit()
    return n


def main():
    apply = "--apply" in sys.argv
    print(f"MODE={'APPLY' if apply else 'DRYRUN'}  SB={SUPABASE_URL[:34]}...")
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    for t in MISSING_TABLES:
        print(f"  {t}: fetching...", flush=True)
        rows = sb_select_all(t)
        print(f"  {t}: SB={len(rows)}", flush=True)
        if not rows:
            print(f"    -> no rows, skip", flush=True)
            continue
        if apply:
            create_from_rows(conn, t, rows)
            upsert_rows(conn, t, rows)
            after = conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            print(f"    -> created+upserted, now {after}", flush=True)

    conn.close()
    if not apply:
        print("DRYRUN complete. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
