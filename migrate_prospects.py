#!/usr/bin/env python3
"""Migrate unmigrated prospects from HOST backup CSV into Supabase `prospects`.

Dedupes by (business_name, niche, metro). Only inserts rows NOT already present.
PostgREST only. Batch inserts <=1000. Does NOT delete anything.
"""
from __future__ import annotations
import csv
import sys
import empire_os.sb as sb

CSV_PATH = "/root/prospects_migrate.csv"
BATCH = 1000


def existing_keys() -> set:
    keys = set()
    off = 0
    while True:
        rows = sb.select("prospects", columns="business_name,niche,metro",
                         limit=1000, offset=off, order="id")
        if not rows:
            break
        for r in rows:
            keys.add((r.get("business_name"), r.get("niche"), r.get("metro")))
        if len(rows) < 1000:
            break
        off += 1000
    return keys


def main() -> None:
    print("Loading existing Supabase prospect keys...")
    have = existing_keys()
    print(f"  existing Supabase prospects: {len(have)}")

    print(f"Reading CSV {CSV_PATH} ...")
    to_insert = []
    seen_keys = set()
    total_csv = 0
    dup_in_csv = 0
    already = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_csv += 1
            key = (row.get("business_name"), row.get("niche"), row.get("metro"))
            if key in seen_keys:
                dup_in_csv += 1
                continue
            seen_keys.add(key)
            if key in have:
                already += 1
                continue
            # strip empty strings -> None so Postgres gets NULLs not ''
            clean = {}
            for k, v in row.items():
                if v is None or v == "":
                    clean[k] = None
                else:
                    clean[k] = v
            # drop id/created_at: let Postgres auto-generate
            clean.pop("id", None)
            clean.pop("created_at", None)
            to_insert.append(clean)

    print(f"  CSV rows: {total_csv} (intra-csv dups skipped: {dup_in_csv})")
    print(f"  already in Supabase: {already}")
    print(f"  NEW to insert: {len(to_insert)}")

    inserted = 0
    for i in range(0, len(to_insert), BATCH):
        batch = to_insert[i:i + BATCH]
        try:
            sb.insert("prospects", batch, return_repr=False)
        except Exception as e:
            print(f"ERROR inserting batch {i}-{i+len(batch)}: {e}")
            sys.exit(1)
        inserted += len(batch)
        print(f"  inserted {inserted}/{len(to_insert)}")

    print(f"DONE. Inserted {inserted} new prospects into Supabase.")


if __name__ == "__main__":
    main()
