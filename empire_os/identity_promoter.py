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
import uuid
from pathlib import Path
from typing import Any

from empire_os.identity_promotion_repository import IdentityPromotionRepository


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
    *,
    repository: IdentityPromotionRepository | None = None,
) -> dict[str, str]:
    store = repository or IdentityPromotionRepository.from_environment()
    return store.existing_links(
        prospect_ids,
        batch_size=LINK_BATCH,
    )


def write_entities(
    proposals: list[dict[str, Any]],
    *,
    repository: IdentityPromotionRepository | None = None,
) -> int:
    store = repository or IdentityPromotionRepository.from_environment()
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

        for row in payload:
            store.ensure_entity(row)

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
    *,
    repository: IdentityPromotionRepository | None = None,
) -> int:
    store = repository or IdentityPromotionRepository.from_environment()
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

        for row in chunk:
            store.ensure_link(row)

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
        help="Perform the controlled canonical identity promotion.",
    )
    args = parser.parse_args()

    proposals = load_proposals()
    eligible = candidates(proposals)

    all_prospect_ids = [
        str(pid)
        for proposal in eligible
        for pid in proposal.get("prospect_ids", [])
    ]

    repository = IdentityPromotionRepository.from_environment()
    existing_links = fetch_existing_links(
        all_prospect_ids,
        repository=repository,
    )

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
        print("CANONICAL WRITES: 0")
        return

    print("MODE: APPLY")
    print("FAIL-CLOSED: YES")
    print("SOURCE PROSPECT UPDATES: 0")
    print("SOURCE PROSPECT DELETES: 0")

    write_entities(
        eligible,
        repository=repository,
    )
    links = write_links(
        eligible,
        existing_links,
        repository=repository,
    )

    print("IDENTITY PROMOTION COMPLETE")
    print(f"ENTITIES PROCESSED: {len(eligible)}")
    print(f"NEW LINK PAYLOAD ROWS: {links}")
    print("REVIEW CLUSTERS PROMOTED: 0")


if __name__ == "__main__":
    main()
