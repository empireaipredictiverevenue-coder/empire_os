#!/usr/bin/env python3
"""Refresh Phase 4 Commercial Exchange snapshot from canonical EmpireDB truth."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from empire_os.buyer_allocation import fetch_buyer_rows
from empire_os.buyer_allocation_repository import (
    BUYER_COLUMNS,
    IDENTITY_COLUMNS,
    QUALIFICATION_COLUMNS,
    BuyerAllocationDataRepository,
)
from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    empiredb_gateway_from_environment,
)
from empire_os.commercial_exchange_inventory import (
    build_exchange_snapshot,
    write_exchange_snapshot,
)
from empire_os.data_query import DataFilter, OrderSpec
from empire_os.niche_taxonomy import normalise
from empire_os.lead_scoring_v2 import MIN_DECISION_CONFIDENCE


PROSPECT_COLUMNS = "id,business_name,niche,metro,created_at,status"
FULFILMENT_COLUMNS = "prospect_id,state"
SOURCE = "canonical_empiredb_projection"


def fetch_qualified_candidate_ids(
    gateway: CanonicalDataGateway,
    limit: int,
) -> list[str]:
    bounded = max(1, min(int(limit), 500))
    rows = gateway.query(
        "prospect_qualifications",
        "prospect_id,evidence_confidence,scored_at",
        filters=(
            DataFilter.eq("scoring_engine", "empire_os.lead_scoring"),
            DataFilter.eq("scoring_version", "v2"),
            DataFilter.eq("status", "scored"),
            DataFilter.in_("tier", ("hot", "warm")),
            DataFilter.gte("evidence_confidence", MIN_DECISION_CONFIDENCE),
        ),
        order=(
            OrderSpec("evidence_confidence", descending=True, nulls_last=True),
            OrderSpec("scored_at", descending=True, nulls_last=True),
            OrderSpec("prospect_id", descending=False),
        ),
        limit=bounded,
    )
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        pid = str(row.get("prospect_id") or "").strip()
        if pid and pid not in seen:
            ids.append(pid)
            seen.add(pid)
    return ids


def fetch_prospects_by_ids(
    gateway: CanonicalDataGateway,
    prospect_ids: list[str],
) -> list[dict[str, Any]]:
    if not prospect_ids:
        return []
    rows = gateway.query(
        "prospects",
        PROSPECT_COLUMNS,
        filters=(DataFilter.in_("id", prospect_ids),),
        limit=len(prospect_ids),
    )
    by_id = {
        str(row.get("id") or "").strip(): dict(row)
        for row in rows
        if str(row.get("id") or "").strip()
    }
    return [by_id[pid] for pid in prospect_ids if pid in by_id]


def fetch_qualification_map(
    gateway: CanonicalDataGateway,
    prospect_ids: list[str],
) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {
        pid: None for pid in prospect_ids
    }
    if not prospect_ids:
        return result

    rows = gateway.query(
        "prospect_qualifications",
        QUALIFICATION_COLUMNS,
        filters=(
            DataFilter.in_("prospect_id", prospect_ids),
            DataFilter.eq("scoring_engine", "empire_os.lead_scoring"),
            DataFilter.in_("scoring_version", ("v2", "v1")),
        ),
        order=(OrderSpec("scored_at", descending=True),),
        limit=max(2, min(len(prospect_ids) * 2, 1000)),
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pid = str(row.get("prospect_id") or "").strip()
        if pid:
            grouped[pid].append(row)

    for pid, candidates in grouped.items():
        for version in ("v2", "v1"):
            chosen = next(
                (
                    row for row in candidates
                    if normalise(row.get("scoring_version") or "v1") == version
                ),
                None,
            )
            if chosen is not None:
                result[pid] = chosen
                break
    return result


def fetch_identity_map(
    gateway: CanonicalDataGateway,
    prospect_ids: list[str],
) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {
        pid: None for pid in prospect_ids
    }
    if not prospect_ids:
        return result

    rows = gateway.query(
        "prospect_entity_links",
        IDENTITY_COLUMNS,
        filters=(
            DataFilter.in_("prospect_id", prospect_ids),
            DataFilter.eq("active", True),
        ),
        order=(OrderSpec("created_at", descending=True),),
        limit=max(2, min(len(prospect_ids) * 2, 1000)),
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pid = str(row.get("prospect_id") or "").strip()
        if pid:
            grouped[pid].append(row)

    for pid, candidates in grouped.items():
        # Fail closed if identity is ambiguous.
        if len(candidates) == 1:
            result[pid] = candidates[0]
    return result


def fetch_allocated_prospect_ids(
    gateway: CanonicalDataGateway,
    prospect_ids: list[str],
) -> set[str]:
    if not prospect_ids:
        return set()

    rows = gateway.query(
        "fulfilment_orders",
        FULFILMENT_COLUMNS,
        filters=(
            DataFilter.in_("prospect_id", prospect_ids),
            DataFilter.not_in("state", ("rejected", "cancelled")),
        ),
        limit=max(1, min(len(prospect_ids) * 2, 1000)),
    )
    return {
        str(row.get("prospect_id") or "").strip()
        for row in rows
        if str(row.get("prospect_id") or "").strip()
    }


def build_runtime_snapshot(
    gateway: CanonicalDataGateway,
    *,
    limit: int,
) -> dict[str, Any]:
    prospect_ids = fetch_qualified_candidate_ids(gateway, limit)
    prospects = fetch_prospects_by_ids(gateway, prospect_ids)
    prospect_ids = [
        str(row.get("id") or "").strip()
        for row in prospects
        if str(row.get("id") or "").strip()
    ]
    qualifications = fetch_qualification_map(gateway, prospect_ids)
    identity_links = fetch_identity_map(gateway, prospect_ids)
    buyers = fetch_buyer_rows(BuyerAllocationDataRepository(gateway))
    allocated = fetch_allocated_prospect_ids(gateway, prospect_ids)

    snapshot = build_exchange_snapshot(
        prospects=prospects,
        qualifications=qualifications,
        identity_links=identity_links,
        buyers=buyers,
        allocated_prospect_ids=allocated,
    )
    snapshot["source"] = SOURCE
    snapshot["candidate_selection"] = "qualification_driven"
    snapshot["qualified_candidates_selected"] = len(prospect_ids)
    snapshot["qualified_v2_candidates_selected"] = len(prospect_ids)
    snapshot["qualified_v1_fallback_candidates_selected"] = 0
    snapshot["prospects_scanned"] = len(prospects)
    snapshot["qualification_rows_available"] = sum(
        value is not None for value in qualifications.values()
    )
    snapshot["identity_links_available"] = sum(
        value is not None for value in identity_links.values()
    )
    snapshot["buyers_scanned"] = len(buyers)
    snapshot["canonical_backend"] = gateway.snapshot().primary_backend.value
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    gateway = empiredb_gateway_from_environment()
    snapshot = build_runtime_snapshot(gateway, limit=args.limit)
    write_exchange_snapshot(Path(args.repo_root), snapshot)
    print(json.dumps({
        "ok": True,
        "source": snapshot["source"],
        "canonical_backend": snapshot["canonical_backend"],
        "candidate_selection": snapshot["candidate_selection"],
        "qualified_candidates_selected": snapshot["qualified_candidates_selected"],
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
