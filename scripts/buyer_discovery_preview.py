#!/usr/bin/env python3
"""OBSERVE-only canonical buyer discovery preview.

Reads canonical Supabase prospects/entity links, ranks locally, and optionally
probes a small number of public company websites. Performs no database writes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from empire_os.buyer_discovery import select_candidates
from empire_os.niche_taxonomy import metro_key, niche_family


def _load_env():
    path = Path("/srv/empire_os/.env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _pages(select_fn, table, columns, *, filters=None, batch=1000, max_rows=50000):
    rows = []
    offset = 0
    while len(rows) < max_rows:
        page = select_fn(table, columns=columns, filters=filters,
                         limit=min(batch, max_rows-len(rows)), offset=offset)
        if not page:
            break
        rows.extend(page)
        if len(page) < batch:
            break
        offset += len(page)
    return rows


def load_rows():
    _load_env()
    from empire_os import sb
    if not sb._configured():
        raise RuntimeError("canonical Supabase configuration required")
    prospects = _pages(
        sb.select, "prospects",
        "id,business_name,niche,metro,phone,website,buy_signal_score,status,notes,contact_name,contact_title,contact_source,contacted_status",
    )
    links = _pages(
        sb.select, "prospect_entity_links", "prospect_id,entity_id,match_score,active",
        filters={"active": "true"},
    )
    entity_by_prospect = {str(row["prospect_id"]): str(row["entity_id"]) for row in links}
    for row in prospects:
        row["entity_id"] = entity_by_prospect.get(str(row.get("id")), "")
    return prospects


def filter_market_rows(rows, *, niche="", metro=""):
    target_family = niche_family(niche) if str(niche or "").strip() else ""
    target_metro = metro_key(metro) if str(metro or "").strip() else ""
    selected = []
    for row in rows:
        if target_family and niche_family(row.get("niche")) != target_family:
            continue
        if target_metro and metro_key(row.get("metro")) != target_metro:
            continue
        selected.append(row)
    return selected


def public_candidate(candidate):
    value = candidate.to_dict()
    return {
        "prospect_id": value["prospect_id"],
        "entity_id": value["entity_id"],
        "business_name": value["business_name"],
        "niche": value["niche"],
        "metro": value["metro"],
        "website": value["website"],
        "decision_role": value["decision_role"],
        "company_score": value["company_score"],
        "offer_key": value["offer_key"],
        "has_named_contact": value["evidence"]["has_named_contact"],
        "mode": "OBSERVE",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Empire real-buyer discovery preview")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--min-score", type=float, default=50.0)
    p.add_argument("--niche", default="",
                   help="optional target niche/family, e.g. roofing")
    p.add_argument("--metro", default="",
                   help="optional target metro, e.g. Austin, TX")
    p.add_argument("--probe", type=int, default=0,
                   help="probe public websites for up to N top candidates")
    p.add_argument("--probe-timeout", type=float, default=10.0,
                   help="hard per-site child-process timeout in seconds")
    args = p.parse_args(argv)
    source_rows = load_rows()
    rows = filter_market_rows(
        source_rows,
        niche=args.niche,
        metro=args.metro,
    )
    candidates = select_candidates(
        rows,
        min_score=args.min_score,
        limit=args.limit,
    )
    output = {
        "mode": "OBSERVE",
        "write_authorized": False,
        "source_rows": len(source_rows),
        "market_rows": len(rows),
        "target_niche": args.niche or None,
        "target_metro": args.metro or None,
        "candidate_count": len(candidates),
        "candidates": [public_candidate(c) for c in candidates],
    }
    if args.probe:
        enriched = []
        timeout = max(2.0, min(float(args.probe_timeout), 30.0))
        for candidate in candidates[:max(0, min(args.probe, 50))]:
            row = candidate.to_dict()
            row["id"] = row.pop("prospect_id")
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "empire_os.buyer_probe_worker"],
                    input=json.dumps(row), text=True, capture_output=True,
                    timeout=timeout, check=False, cwd="/srv/empire_os",
                )
                if proc.returncode == 0:
                    enriched.append(json.loads(proc.stdout))
                else:
                    enriched.append({"prospect_id": candidate.prospect_id,
                                     "business_name": candidate.business_name,
                                     "site_ok": False, "outreach_ready": False,
                                     "rejection_reason": "probe_failed"})
            except subprocess.TimeoutExpired:
                enriched.append({"prospect_id": candidate.prospect_id,
                                 "business_name": candidate.business_name,
                                 "site_ok": False, "outreach_ready": False,
                                 "rejection_reason": "site_timeout"})
        output["site_probe"] = enriched
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
