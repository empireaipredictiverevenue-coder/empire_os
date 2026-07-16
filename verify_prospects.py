#!/usr/bin/env python3
"""Final verification: accurate Supabase counts + rigorous CSV->Supabase delta.

Counts rows via id-ordered pagination (stable). Computes unique
(business_name, niche, metro) keys to dedupe. Reports CSV prospects that are
NOT already in Supabase `prospects`.
"""
from __future__ import annotations
import csv
import empire_os.sb as sb

CSV_PATH = "/root/prospects_migrate.csv"
BATCH = 1000


def count_rows(table: str) -> int:
    total = 0
    off = 0
    while True:
        r = sb.select(table, columns="id", limit=BATCH, offset=off, order="id")
        if not r:
            break
        total += len(r)
        if len(r) < BATCH:
            break
        off += BATCH
    return total


def supabase_unique_keys() -> set:
    keys = set()
    off = 0
    while True:
        r = sb.select("prospects", columns="business_name,niche,metro",
                      limit=BATCH, offset=off, order="id")
        if not r:
            break
        for x in r:
            keys.add((x.get("business_name"), x.get("niche"), x.get("metro")))
        if len(r) < BATCH:
            break
        off += BATCH
    return keys


def csv_unique_keys() -> tuple[set, int, int]:
    keys = set()
    total = 0
    dups = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            k = (row.get("business_name"), row.get("niche"), row.get("metro"))
            if k in keys:
                dups += 1
                continue
            keys.add(k)
    return keys, total, dups


def main() -> None:
    print("=== Supabase row counts (id-ordered pagination) ===")
    for t in ["contractors", "enriched_leads", "b2b_leads", "prospects"]:
        print(f"  {t}: {count_rows(t)} rows")

    print("\n=== Prospects delta (CSV vs Supabase) ===")
    sb_keys = supabase_unique_keys()
    print(f"  Supabase prospects: {count_rows('prospects')} rows, "
          f"{len(sb_keys)} unique (business_name,niche,metro) keys")
    csv_keys, csv_total, csv_dups = csv_unique_keys()
    print(f"  CSV: {csv_total} rows, {csv_dups} intra-file dups, "
          f"{len(csv_keys)} unique keys")
    missing = csv_keys - sb_keys
    print(f"  CSV unique keys NOT in Supabase: {len(missing)}")
    if missing:
        for k in list(missing)[:10]:
            print("    MISSING:", k)


if __name__ == "__main__":
    main()
