"""Migrate unmigrated prospects from CSV into Supabase `prospects` via PostgREST.

Reads /root/empire_os/prospects_migrate.csv, diffs against existing prospect ids
in Supabase, and batch-inserts the missing rows (<=1000 per request).
PostgREST-only. No deletes. Idempotent (skips existing ids).
"""
from __future__ import annotations
import csv, json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
import empire_os.sb as sb
import urllib.request

CSV_PATH = "/root/empire_os/prospects_migrate.csv"
TABLE = "prospects"
BATCH = 1000

COLS = ["id","created_at","business_name","niche","metro","phone","website",
        "address","rating","review_count","buy_signal_score","runs_ads","status",
        "notes","contacted_at","contact_name","contact_title","contact_source",
        "contacted_status"]

def fetch_existing_ids():
    ids = set()
    offset = 0
    while True:
        rows = sb.select(TABLE, columns="id", limit=1000, offset=offset)
        if not rows:
            break
        for r in rows:
            ids.add(r["id"])
        if len(rows) < 1000:
            break
        offset += 1000
    return ids

def batch_insert(rows):
    url = f"{sb.SUPABASE_URL}/rest/v1/{TABLE}"
    headers = sb._headers({"Prefer": "return=minimal"})
    data = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] loading CSV {CSV_PATH}", flush=True)
    existing = fetch_existing_ids()
    print(f"  existing prospect ids in Supabase: {len(existing)}", flush=True)

    missing = []
    total = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            pid = (row.get("id") or "").strip()
            if not pid or pid in existing:
                continue
            rec = {}
            for c in COLS:
                v = row.get(c)
                rec[c] = None if v in (None, "") else v
            missing.append(rec)

    print(f"  CSV rows: {total}, missing (to insert): {len(missing)}", flush=True)

    inserted = 0
    for i in range(0, len(missing), BATCH):
        chunk = missing[i:i+BATCH]
        try:
            st = batch_insert(chunk)
            inserted += len(chunk)
            print(f"  inserted batch {i//BATCH+1}: {len(chunk)} rows (HTTP {st}) total {inserted}", flush=True)
        except Exception as e:
            print(f"  BATCH FAIL at {i}: {e}", flush=True)
            # retry once with smaller slices?
            for rec in chunk:
                try:
                    sb.insert(TABLE, rec, return_repr=False)
                    inserted += 1
                except Exception as e2:
                    print(f"    row fail {rec.get('id')}: {e2}", flush=True)
        time.sleep(0.2)

    print(f"DONE. inserted={inserted} of {len(missing)} missing", flush=True)

if __name__ == "__main__":
    main()
