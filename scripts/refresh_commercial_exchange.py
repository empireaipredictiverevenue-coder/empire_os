#!/usr/bin/env python3
"""Refresh Phase 4 Commercial Exchange snapshot from canonical Supabase truth."""
from __future__ import annotations

import argparse
import json
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any

from empire_os.buyer_allocation import fetch_buyer_rows
from empire_os.commercial_exchange_inventory import (
    build_exchange_snapshot,
    write_exchange_snapshot,
)
from empire_os.qualification_worker_v2 import request_json
from empire_os.niche_taxonomy import normalise


def reader(path: str, params: dict[str, str]) -> Any:
    query = urllib.parse.urlencode(params)
    return request_json("GET", f"{path}?{query}")


def fetch_prospects(limit: int) -> list[dict[str, Any]]:
    rows = reader(
        "/rest/v1/prospects",
        {
            "select": "id,business_name,niche,metro,created_at,status",
            "order": "created_at.desc",
            "limit": str(max(1, min(int(limit), 500))),
        },
    )
    return [row for row in (rows or []) if isinstance(row, dict)]


def _in_filter(ids: list[str]) -> str:
    return "in.(" + ",".join(ids) + ")"


def fetch_qualification_map(
    prospect_ids: list[str],
) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {
        pid: None for pid in prospect_ids
    }
    if not prospect_ids:
        return result

    rows = reader(
        "/rest/v1/prospect_qualifications",
        {
            "select": (
                "id,prospect_id,entity_id,score,tier,status,"
                "scoring_engine,scoring_version,evidence_confidence,"
                "observed_dimensions,unknown_dimensions,scored_at"
            ),
            "prospect_id": _in_filter(prospect_ids),
            "scoring_engine": "eq.empire_os.lead_scoring",
            "scoring_version": "in.(v2,v1)",
            "order": "scored_at.desc",
            "limit": str(max(2, len(prospect_ids) * 2)),
        },
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("prospect_id") or "").strip()
        if pid:
            grouped[pid].append(row)

    for pid, candidates in grouped.items():
        for version in ("v2", "v1"):
            chosen = next(
                (
                    row for row in candidates
                    if normalise(
                        row.get("scoring_version") or "v1"
                    ) == version
                ),
                None,
            )
            if chosen is not None:
                result[pid] = chosen
                break
    return result


def fetch_identity_map(
    prospect_ids: list[str],
) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {
        pid: None for pid in prospect_ids
    }
    if not prospect_ids:
        return result

    rows = reader(
        "/rest/v1/prospect_entity_links",
        {
            "select": (
                "prospect_id,entity_id,match_score,active,created_at"
            ),
            "prospect_id": _in_filter(prospect_ids),
            "active": "eq.true",
            "order": "created_at.desc",
            "limit": str(max(2, len(prospect_ids) * 2)),
        },
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("prospect_id") or "").strip()
        if pid:
            grouped[pid].append(row)

    for pid, candidates in grouped.items():
        # Fail closed if identity is ambiguous.
        if len(candidates) == 1:
            result[pid] = candidates[0]
    return result


def fetch_allocated_prospect_ids(
    prospect_ids: list[str],
) -> set[str]:
    if not prospect_ids:
        return set()

    rows = reader(
        "/rest/v1/fulfilment_orders",
        {
            "select": "prospect_id,state",
            "prospect_id": _in_filter(prospect_ids),
            "state": "not.in.(rejected,cancelled)",
            "limit": str(max(1, len(prospect_ids) * 2)),
        },
    )
    return {
        str(row.get("prospect_id") or "").strip()
        for row in (rows or [])
        if isinstance(row, dict)
        and str(row.get("prospect_id") or "").strip()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    prospects = fetch_prospects(args.limit)
    prospect_ids = [
        str(row.get("id") or "").strip()
        for row in prospects
        if str(row.get("id") or "").strip()
    ]

    qualifications = fetch_qualification_map(prospect_ids)
    identity_links = fetch_identity_map(prospect_ids)
    buyers = fetch_buyer_rows(reader)
    allocated = fetch_allocated_prospect_ids(prospect_ids)

    snapshot = build_exchange_snapshot(
        prospects=prospects,
        qualifications=qualifications,
        identity_links=identity_links,
        buyers=buyers,
        allocated_prospect_ids=allocated,
    )
    snapshot["prospects_scanned"] = len(prospects)
    snapshot["qualification_rows_available"] = sum(
        value is not None for value in qualifications.values()
    )
    snapshot["identity_links_available"] = sum(
        value is not None for value in identity_links.values()
    )
    snapshot["buyers_scanned"] = len(buyers)

    write_exchange_snapshot(Path(args.repo_root), snapshot)
    print(json.dumps({
        "ok": True,
        "prospects_scanned": snapshot["prospects_scanned"],
        "inventory_count": snapshot["inventory_count"],
        "overflow_count": snapshot["overflow_count"],
        "allocation_candidate_count": snapshot[
            "allocation_candidate_count"
        ],
        "buyer_seat_count": snapshot["buyer_seat_count"],
        "corridor_count": snapshot["corridor_count"],
        "supply_gate_diagnostics": snapshot[
            "supply_gate_diagnostics"
        ],
        "seat_activation_blocker_counts": snapshot[
            "seat_activation_blocker_counts"
        ],
        "automatic_external_delivery": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
