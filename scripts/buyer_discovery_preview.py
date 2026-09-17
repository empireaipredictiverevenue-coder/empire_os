#!/usr/bin/env python3
"""OBSERVE-only canonical buyer discovery preview.

Reads canonical Supabase prospects/entity links, ranks locally, and optionally
probes a small number of public company websites. Performs no database writes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from empire_os.buyer_discovery import enrich_candidate, select_candidates
from empire_os.search_fabric.site_probe import probe_site


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
    p.add_argument("--probe", type=int, default=0,
                   help="probe public websites for up to N top candidates")
    args = p.parse_args(argv)
    rows = load_rows()
    candidates = select_candidates(rows, min_score=args.min_score, limit=args.limit)
    output = {
        "mode": "OBSERVE", "write_authorized": False,
        "source_rows": len(rows), "candidate_count": len(candidates),
        "candidates": [public_candidate(c) for c in candidates],
    }
    if args.probe:
        enriched = []
        for candidate in candidates[:max(0, min(args.probe, 20))]:
            evidence = probe_site(candidate.website, max_pages=4)
            result = enrich_candidate(candidate, evidence)
            enriched.append({
                "prospect_id": candidate.prospect_id,
                "business_name": candidate.business_name,
                "site_ok": bool(evidence.get("ok")),
                "site_evidence_score": evidence.get("evidence_score"),
                "decision_maker_found": bool(result.get("decision_maker")),
                "email_candidates_found": len(result.get("contact_email_candidates") or []),
            })
        output["site_probe"] = enriched
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
