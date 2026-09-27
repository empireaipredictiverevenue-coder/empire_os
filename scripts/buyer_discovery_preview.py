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

from empire_os.buyer_discovery import (
    accepted_acquisition_website,
    select_candidates,
)
from empire_os.niche_taxonomy import metro_key, niche_family
from empire_os.runtime_env import load_runtime_env

ENV_PATH = os.environ.get(
    "EMPIRE_BUYER_DISCOVERY_ENV_PATH",
    "/srv/empire_os/runtime/secrets/outbound.env",
)


def _load_env(path: str | Path = ENV_PATH) -> dict[str, str]:
    return load_runtime_env(
        path,
        required=("SUPABASE_URL", "SUPABASE_SERVICE_KEY"),
    )


def _supabase_client():
    from empire_os import sb

    if sb._configured():
        return sb

    env = _load_env()
    sb.SUPABASE_URL = env["SUPABASE_URL"].rstrip("/")
    sb.SUPABASE_KEY = env["SUPABASE_SERVICE_KEY"]
    if not sb._configured():
        raise RuntimeError("canonical Supabase configuration required")
    return sb


def _pages(
    select_fn,
    table,
    columns,
    *,
    filters=None,
    order=None,
    batch=1000,
    max_rows=50000,
):
    rows = []
    offset = 0
    while len(rows) < max_rows:
        page = select_fn(
            table,
            columns=columns,
            filters=filters,
            order=order,
            limit=min(batch, max_rows-len(rows)),
            offset=offset,
        )
        if not page:
            break
        rows.extend(page)
        if len(page) < batch:
            break
        offset += len(page)
    return rows


def load_rows():
    sb = _supabase_client()
    prospects = _pages(
        sb.select, "prospects",
        "id,business_name,niche,metro,phone,website,buy_signal_score,status,notes,contact_name,contact_title,contact_source,contacted_status",
    )
    links = _pages(
        sb.select,
        "prospect_entity_links",
        "prospect_id,entity_id,match_score,active",
        filters={"active": "true"},
    )
    acquisitions = _pages(
        sb.select,
        "prospect_acquisitions",
        "prospect_id,evidence,created_at",
        order="created_at.desc",
    )
    entity_by_prospect = {
        str(row["prospect_id"]): str(row["entity_id"])
        for row in links
    }
    acquisition_by_prospect = {}
    for acquisition in acquisitions:
        prospect_id = str(acquisition.get("prospect_id") or "")
        if not prospect_id or prospect_id in acquisition_by_prospect:
            continue
        evidence = acquisition.get("evidence")
        if accepted_acquisition_website(evidence):
            acquisition_by_prospect[prospect_id] = evidence

    for row in prospects:
        prospect_id = str(row.get("id") or "")
        row["entity_id"] = entity_by_prospect.get(prospect_id, "")
        evidence = acquisition_by_prospect.get(prospect_id)
        if evidence:
            row["_acquisition_evidence"] = evidence
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
            inner_budget = max(2.0, timeout - 5.0)
            row["_probe_options"] = {
                "max_pages": 7,
                "request_timeout": min(4.0, max(1.5, inner_budget / 3.0)),
                "time_budget_seconds": inner_budget,
            }
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
