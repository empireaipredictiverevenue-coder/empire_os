#!/usr/bin/env python3
"""Empire OS canonical identity resolver.

DRY-RUN BY DEFAULT.
Reads canonical prospects through the Empire Data Gateway and proposes
canonical business entities without writing anything back.

The resolver:
- preserves every source prospect
- clusters exact business+niche+metro identities
- measures phone/website/status conflicts
- emits a review-safe proposal report
- never updates/deletes prospects
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from empire_os.canonical_data_gateway import gateway_from_environment
from empire_os.identity_resolver_repository import IdentityResolverDataRepository
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"
REPORT_PATH = Path(
    os.environ.get(
        "IDENTITY_DRY_RUN_REPORT",
        "/srv/empire_os/runtime/identity/identity_dry_run.json",
    )
)


def _repository() -> IdentityResolverDataRepository:
    return IdentityResolverDataRepository(
        gateway_from_environment(load_runtime_env(ENV_PATH))
    )


def fetch_prospects(
    repository: IdentityResolverDataRepository | None = None,
) -> list[dict[str, Any]]:
    return (repository or _repository()).fetch_prospects()


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def phone_norm(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) >= 10 else digits


def website_norm(value: Any) -> str:
    value = str(value or "").lower().strip()
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"^www\.", "", value)
    return value.rstrip("/")


def cluster_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        norm(row.get("business_name")),
        norm(row.get("niche")),
        norm(row.get("metro")),
    )


def proposal_id(key: tuple[str, str, str]) -> str:
    raw = "|".join(key).encode()
    return "be_" + hashlib.sha256(raw).hexdigest()[:20]


def main() -> None:
    repository = _repository()
    rows = fetch_prospects(repository)

    clusters: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    singleton_count = 0

    for row in rows:
        key = cluster_key(row)
        if all(key):
            clusters[key].append(row)
        else:
            singleton_count += 1

    duplicate_clusters = {
        key: members
        for key, members in clusters.items()
        if len(members) > 1
    }

    proposals: list[dict[str, Any]] = []
    status_mix = Counter()
    review_cluster_count = 0
    linked_row_count = 0

    for key, members in clusters.items():
        statuses = sorted(
            {str(r.get("status") or "<NULL>").strip() for r in members}
        )
        phones = sorted(
            {
                phone_norm(r.get("phone"))
                for r in members
                if phone_norm(r.get("phone"))
            }
        )
        websites = sorted(
            {
                website_norm(r.get("website"))
                for r in members
                if website_norm(r.get("website"))
            }
        )

        duplicate = len(members) > 1
        status_conflict = len(statuses) > 1
        phone_conflict = len(phones) > 1
        website_conflict = len(websites) > 1
        needs_review = status_conflict or phone_conflict or website_conflict

        if duplicate:
            linked_row_count += len(members)
            if needs_review:
                review_cluster_count += 1
            if status_conflict:
                status_mix[tuple(statuses)] += 1

        if len(members) == 1:
            resolution_state = "unresolved"
            method = "singleton_exact_identity"
        elif needs_review:
            resolution_state = "review"
            method = "exact_identity_with_conflicts"
        else:
            resolution_state = "resolved_candidate"
            method = "exact_business_niche_metro"

        proposals.append(
            {
                "entity_proposal_id": proposal_id(key),
                "resolution_state": resolution_state,
                "match_method": method,
                "source_row_count": len(members),
                "prospect_ids": [str(r["id"]) for r in members],
                "canonical_name_candidate": members[0].get("business_name"),
                "canonical_niche_candidate": members[0].get("niche"),
                "canonical_metro_candidate": members[0].get("metro"),
                "status_values": statuses,
                "phone_variants": len(phones),
                "website_variants": len(websites),
                "conflicts": {
                    "status": status_conflict,
                    "phone": phone_conflict,
                    "website": website_conflict,
                },
            }
        )

    proposals.sort(
        key=lambda item: (
            item["resolution_state"] != "review",
            -item["source_row_count"],
        )
    )

    report = {
        "schema_version": "identity_resolver.dry_run.v1",
        "dry_run": True,
        "data_source": repository.snapshot(),
        "source_table": "prospects",
        "total_prospects": len(rows),
        "identity_complete_rows": len(rows) - singleton_count,
        "rows_with_missing_identity_key_component": singleton_count,
        "exact_identity_clusters": len(clusters),
        "duplicate_clusters": len(duplicate_clusters),
        "duplicate_rows": sum(
            len(members) - 1 for members in duplicate_clusters.values()
        ),
        "review_clusters": review_cluster_count,
        "candidate_resolved_clusters": sum(
            1
            for item in proposals
            if item["resolution_state"] == "resolved_candidate"
            and item["source_row_count"] > 1
        ),
        "status_mix_patterns": {
            " + ".join(pattern): count
            for pattern, count in status_mix.most_common()
        },
        "writes_performed": 0,
        "deletes_performed": 0,
        "prospect_rows_modified": 0,
        "proposals": proposals,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    print("IDENTITY RESOLVER: DRY RUN")
    print(f"PROSPECTS: {report['total_prospects']}")
    print(f"EXACT IDENTITY CLUSTERS: {report['exact_identity_clusters']}")
    print(f"DUPLICATE CLUSTERS: {report['duplicate_clusters']}")
    print(f"DUPLICATE ROWS: {report['duplicate_rows']}")
    print(f"REVIEW CLUSTERS: {report['review_clusters']}")
    print(
        "CANDIDATE RESOLVED CLUSTERS: "
        f"{report['candidate_resolved_clusters']}"
    )
    print("CANONICAL DATA WRITES: 0")
    print("PROSPECT ROWS MODIFIED: 0")
    print(f"REPORT: {REPORT_PATH}")


if __name__ == "__main__":
    main()
