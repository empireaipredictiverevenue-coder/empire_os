#!/usr/bin/env python3
"""Empire OS canonical identity promoter.

Default: dry run.
Writes require --apply.

Safety guarantees:
- source prospects are never updated or deleted
- only resolved_candidate proposals are eligible
- review/unresolved proposals are never promoted
- deterministic UUIDs make reruns idempotent
- existing prospect links are validated before any write
- writes are performed in bounded batches
- failures stop immediately
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


ENV_PATH = "/etc/empire_os.env"
REPORT_PATH = Path(
    os.environ.get(
        "IDENTITY_DRY_RUN_REPORT",
        "/srv/empire_os/runtime/identity/identity_dry_run.json",
    )
)

ENTITY_NAMESPACE = uuid.UUID("7f4f5f91-c9e1-4c0e-9d37-7f3cdb6e7f21")
ENTITY_BATCH = 100
LINK_BATCH = 200


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    with open(ENV_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
    return env


ENV = load_env()
BASE = ENV["SUPABASE_URL"].rstrip("/")
KEY = ENV["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": KEY,
    "Authorization": "Bearer " + KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def request_json(
    method: str,
    table: str,
    query: str = "",
    payload: Any | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode()

    req = urllib.request.Request(
        f"{BASE}/rest/v1/{table}{query}",
        data=data,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read().decode()

        if not raw:
            return response.status, None

        return response.status, json.loads(raw)


def deterministic_entity_id(name: str, niche: str, metro: str) -> str:
    key = "|".join(
        (
            name.strip().lower(),
            niche.strip().lower(),
            metro.strip().lower(),
        )
    )
    return str(uuid.uuid5(ENTITY_NAMESPACE, key))


def load_proposals() -> list[dict[str, Any]]:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(
            f"identity_dry_run_report_missing:{REPORT_PATH}"
        )

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    if report.get("dry_run") is not True:
        raise RuntimeError("identity_report_not_dry_run")

    proposals = report.get("proposals")
    if not isinstance(proposals, list):
        raise RuntimeError("identity_report_invalid_proposals")

    return proposals


def candidates(
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        p
        for p in proposals
        if p.get("resolution_state") == "resolved_candidate"
        and int(p.get("source_row_count", 0)) > 1
    ]


def fetch_existing_links(
    prospect_ids: list[str],
) -> dict[str, str]:
    existing: dict[str, str] = {}

    for i in range(0, len(prospect_ids), LINK_BATCH):
        batch = prospect_ids[i:i + LINK_BATCH]
        encoded = ",".join(batch)

        query = "?" + urllib.parse.urlencode(
            {
                "select": "prospect_id,entity_id",
                "prospect_id": f"in.({encoded})",
            }
        )

        _, rows = request_json(
            "GET",
            "prospect_entity_links",
            query,
        )

        for row in rows:
            existing[str(row["prospect_id"])] = str(row["entity_id"])

    return existing


def write_entities(proposals: list[dict[str, Any]]) -> int:
    inserted_or_existing = 0

    for i in range(0, len(proposals), ENTITY_BATCH):
        chunk = proposals[i:i + ENTITY_BATCH]
        payload = []

        for proposal in chunk:
            name = str(proposal["canonical_name_candidate"])
            niche = str(proposal["canonical_niche_candidate"])
            metro = str(proposal["canonical_metro_candidate"])

            payload.append(
                {
                    "id": deterministic_entity_id(name, niche, metro),
                    "canonical_name": name,
                    "normalized_name": name.strip().lower(),
                    "canonical_niche": niche,
                    "canonical_metro": metro,
                    "identity_confidence": 1.0,
                    "resolution_state": "resolved_candidate",
                    "provenance": {
                        "resolver": "identity_resolver.dry_run.v1",
                        "match_method": proposal["match_method"],
                        "source_row_count": proposal["source_row_count"],
                        "generated_from": "exact_business_niche_metro",
                    },
                }
            )

        request_json(
            "POST",
            "business_entities",
            payload=payload,
            extra_headers={
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
        )

        inserted_or_existing += len(payload)

        print(
            f"ENTITY BATCH: "
            f"{min(i + ENTITY_BATCH, len(proposals))}/{len(proposals)}",
            flush=True,
        )

    return inserted_or_existing


def write_links(
    proposals: list[dict[str, Any]],
    existing_links: dict[str, str],
) -> int:
    rows: list[dict[str, Any]] = []

    for proposal in proposals:
        name = str(proposal["canonical_name_candidate"])
        niche = str(proposal["canonical_niche_candidate"])
        metro = str(proposal["canonical_metro_candidate"])

        entity_id = deterministic_entity_id(name, niche, metro)

        evidence = {
            "match_method": proposal["match_method"],
            "match_score": 1.0,
            "source_row_count": proposal["source_row_count"],
            "status_values": proposal.get("status_values", []),
        }

        for prospect_id in proposal["prospect_ids"]:
            prospect_id = str(prospect_id)

            if prospect_id in existing_links:
                if existing_links[prospect_id] != entity_id:
                    raise RuntimeError(
                        "prospect_link_conflict:"
                        f"{prospect_id}:"
                        f"{existing_links[prospect_id]}!="
                        f"{entity_id}"
                    )
                continue

            rows.append(
                {
                    "prospect_id": prospect_id,
                    "entity_id": entity_id,
                    "match_method": proposal["match_method"],
                    "match_score": 1.0,
                    "evidence": evidence,
                    "active": True,
                }
            )

    inserted = 0

    for i in range(0, len(rows), LINK_BATCH):
        chunk = rows[i:i + LINK_BATCH]

        request_json(
            "POST",
            "prospect_entity_links",
            payload=chunk,
            extra_headers={
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
        )

        inserted += len(chunk)

        print(
            f"LINK BATCH: "
            f"{min(i + LINK_BATCH, len(rows))}/{len(rows)}",
            flush=True,
        )

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the controlled Supabase promotion.",
    )
    args = parser.parse_args()

    proposals = load_proposals()
    eligible = candidates(proposals)

    all_prospect_ids = [
        str(pid)
        for proposal in eligible
        for pid in proposal.get("prospect_ids", [])
    ]

    existing_links = fetch_existing_links(all_prospect_ids)

    print("IDENTITY PROMOTER")
    print(f"REPORT: {REPORT_PATH}")
    print(f"TOTAL PROPOSALS: {len(proposals)}")
    print(f"ELIGIBLE CANDIDATES: {len(eligible)}")
    print(f"CANDIDATE PROSPECT ROWS: {len(all_prospect_ids)}")
    print(
        "REVIEW/UNRESOLVED PROPOSALS HELD BACK: "
        f"{len(proposals) - len(eligible)}"
    )
    print(f"EXISTING LINKS: {len(existing_links)}")

    if not args.apply:
        print("MODE: DRY RUN")
        print("SUPABASE WRITES: 0")
        return

    print("MODE: APPLY")
    print("FAIL-CLOSED: YES")
    print("SOURCE PROSPECT UPDATES: 0")
    print("SOURCE PROSPECT DELETES: 0")

    write_entities(eligible)
    links = write_links(eligible, existing_links)

    print("IDENTITY PROMOTION COMPLETE")
    print(f"ENTITIES PROCESSED: {len(eligible)}")
    print(f"NEW LINK PAYLOAD ROWS: {links}")
    print("REVIEW CLUSTERS PROMOTED: 0")


if __name__ == "__main__":
    main()
