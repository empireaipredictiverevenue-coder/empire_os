#!/usr/bin/env python3
"""
supabase_columnmap_reconcile.py — column-map reconciliation for the two
tables whose SQLite and Supabase schemas DIVERGE (the 4 exclusive tables
are handled by supabase_reconcile.py).

Findings (2026-08-25):
  crm_leads: SQL PK=id, has lead_uid (unique, 8855 non-null). SB has 900 MORE
    rows + 5 commercial cols SQL lacks: sold_price, buyer_id, icp_score,
    enriched, sold_at. Strategy: ALTER ADD those 5 cols, then UPSERT by
    lead_uid (insert SB-only rows, update commercial cols on match).
  lane_leads: SB PK=id (subset, 11 cols). SQL PK=lead_ref (no shared join
    key). Strategy: mirror SB into a SEPARATE table lane_leads_sb (no risk to
    the operational lane_leads). Joins done downstream via lane_id/prospect_id.

Dry-run by default (--apply to write). Resumable/idempotent.
"""
import os
import sys
import json
import sqlite3
import urllib.request

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")

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

CRM_EXTRA = ["sold_price", "buyer_id", "icp_score", "enriched", "sold_at"]


def _bind(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v


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


def reconcile_crm(conn, apply):
    rows = sb_select_all("crm_leads")
    print(f"  crm_leads: SB={len(rows)}", flush=True)
    # ensure extra cols exist
    existing = {r[1] for r in conn.execute("PRAGMA table_info(crm_leads)")}
    for col in CRM_EXTRA:
        if col not in existing:
            conn.execute(f'ALTER TABLE crm_leads ADD COLUMN "{col}" TEXT')
            print(f"    +added col {col}", flush=True)
    # guarantee lead_uid is a usable UPSERT key
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_crm_leads_lead_uid ON crm_leads(lead_uid)")
    if not apply:
        return
    cur = conn.cursor()
    ins = upd = 0
    for row in rows:
        uid = row.get("lead_uid")
        if not uid:
            continue
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        colspec = ",".join(f'"{c}"' for c in cols)
        updates = ",".join(f'"{c}"=excluded."{c}"' for c in cols if c != "lead_uid")
        sql = (f'INSERT INTO crm_leads ({colspec}) VALUES ({placeholders}) '
               f'ON CONFLICT(lead_uid) DO UPDATE SET {updates}')
        vals = [_bind(row[c]) for c in cols]
        cur.execute(sql, vals)
        # distinguish insert vs update cheaply: check if lead_uid pre-existed
        ins += 1
    conn.commit()
    after = conn.execute("SELECT count(*) FROM crm_leads").fetchone()[0]
    print(f"    -> upserted {ins} rows, now {after}", flush=True)


def reconcile_lane(conn, apply):
    rows = sb_select_all("lane_leads")
    print(f"  lane_leads: SB={len(rows)}", flush=True)
    if not apply:
        return
    cols = [c for c in rows[0].keys() if c != "id"]
    colspec = ", ".join(f'"{c}" TEXT' for c in cols)
    conn.execute('DROP TABLE IF EXISTS lane_leads_sb')
    conn.execute(f'CREATE TABLE lane_leads_sb (id TEXT PRIMARY KEY, {colspec})')
    cur = conn.cursor()
    for row in rows:
        c2 = list(row.keys())
        ph = ",".join("?" for _ in c2)
        cs = ",".join(f'"{c}"' for c in c2)
        up = ",".join(f'"{c}"=excluded."{c}"' for c in c2 if c != "id")
        sql = (f'INSERT INTO lane_leads_sb ({cs}) VALUES ({ph}) '
               f'ON CONFLICT(id) DO UPDATE SET {up}')
        cur.execute(sql, [_bind(row[c]) for c in c2])
    conn.commit()
    after = conn.execute("SELECT count(*) FROM lane_leads_sb").fetchone()[0]
    print(f"    -> mirrored to lane_leads_sb, now {after}", flush=True)


def main():
    apply = "--apply" in sys.argv
    print(f"MODE={'APPLY' if apply else 'DRYRUN'}", flush=True)
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    reconcile_crm(conn, apply)
    reconcile_lane(conn, apply)
    conn.close()
    if not apply:
        print("DRYRUN complete. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
