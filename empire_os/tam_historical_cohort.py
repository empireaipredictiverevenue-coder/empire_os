#!/usr/bin/env python3
"""Aggregate-only historical TAM/Prospect archive audit; never exports identities.

Reads the existing authorised local September 2026 data-cloud dump as historic
evidence. Never connects to EmpireDB, changes a record, extracts contacts, runs
scoring, contacts anyone, or asserts that archived leads are saleable today.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterator, Mapping

HEADER = re.compile(r'^COPY "public"\."([a-z_]+)" \((.*)\) FROM stdin;$')
TABLES = frozenset((
    "prospects", "prospect_qualifications",
    "prospect_entity_links", "prospect_acquisitions",
))
MAX_DUMP_BYTES = 350_000_000


def archived_rows(path: Path) -> Iterator[tuple[str, dict[str, str | None]]]:
    """Stream only relevant COPY sections; memory holds only IDs and counts."""
    name = None
    columns = []
    with path.open("r", encoding="utf-8", errors="strict") as source:
        for raw in source:
            line = raw.rstrip("\n\r")
            if name is None:
                match = HEADER.fullmatch(line)
                if match:
                    name = match.group(1)
                    columns = [
                        column.strip().strip('"')
                        for column in match.group(2).split(",")
                    ] if name in TABLES else []
                continue
            if line == r"\.":
                name = None
                columns = []
                continue
            if not columns:
                continue
            values = line.split("\t")
            if len(values) != len(columns):
                raise ValueError("archived COPY column count mismatch")
            yield name, {
                key: (None if value == r"\N" else value)
                for key, value in zip(columns, values)
            }


def inspect_archive(
    *,
    dump: Path,
    exchange: Mapping[str, object] | None = None,
    max_bytes: int = MAX_DUMP_BYTES,
) -> dict[str, object]:
    if (
        not dump.is_file()
        or dump.is_symlink()
        or dump.stat().st_size < 100
        or dump.stat().st_size > max_bytes
    ):
        raise ValueError("historic dump unavailable or outside bounded size")
    sector = Counter()
    geo_missing = 0
    status = Counter()
    source_type = Counter()
    prospects: set[str] = set()
    link_prospects: set[str] = set()
    entity_ids: set[str] = set()
    acquired: set[str] = set()
    qualified_any: set[str] = set()
    v1: set[str] = set()
    v2: set[str] = set()
    v2_hot_warm: set[str] = set()
    qualified_by_state = Counter()
    contact_routes = Counter()
    ages = Counter()
    first_seen = last_seen = None
    malformed_qualification = 0

    for table, row in archived_rows(dump):
        pid = str(row.get("prospect_id") or "").strip()
        if table == "prospects":
            pid = str(row.get("id") or "").strip()
            if not pid or pid in prospects:
                raise ValueError("duplicate or missing historical prospect id")
            prospects.add(pid)
            niche = str(row.get("niche") or "").strip().casefold()
            metro = str(row.get("metro") or "").strip().casefold()
            sector[niche or "UNCLASSIFIED"] += 1
            status[str(row.get("status") or "UNKNOWN").strip().casefold()] += 1
            geo_missing += not bool(metro)
            contact_routes["has_business_name"] += bool(str(row.get("business_name") or "").strip())
            contact_routes["has_phone_unverified"] += bool(str(row.get("phone") or "").strip())
            contact_routes["has_website_unverified"] += bool(str(row.get("website") or "").strip())
            contact_routes["has_contact_name_unverified"] += bool(str(row.get("contact_name") or "").strip())
            contact_routes["has_contact_title_unverified"] += bool(str(row.get("contact_title") or "").strip())
            observed = str(row.get("created_at") or "").strip()
            if observed:
                day = observed[:10]
                first_seen = min(first_seen, day) if first_seen else day
                last_seen = max(last_seen, day) if last_seen else day
                ages[day[:7]] += 1
        elif table == "prospect_entity_links":
            if pid and row.get("active") in ("t", "true", "True", "1"):
                link_prospects.add(pid)
                if row.get("entity_id"):
                    entity_ids.add(str(row["entity_id"]))
        elif table == "prospect_acquisitions":
            if pid:
                acquired.add(pid)
            source_type[str(row.get("source") or "UNKNOWN").strip().casefold()] += 1
        elif table == "prospect_qualifications":
            if not pid:
                malformed_qualification += 1
                continue
            qualified_any.add(pid)
            version = str(row.get("scoring_version") or "").strip().casefold()
            engine = str(row.get("scoring_engine") or "").strip()
            scored_state = str(row.get("status") or "").strip().casefold()
            tier = str(row.get("tier") or "").strip().casefold()
            qualified_by_state[f"{version}:{scored_state}"] += 1
            if version == "v1":
                v1.add(pid)
            if version == "v2" and engine == "empire_os.lead_scoring":
                v2.add(pid)
                try:
                    confidence = float(row.get("evidence_confidence") or 0)
                except (ValueError, TypeError):
                    confidence = 0
                if scored_state == "scored" and tier in ("hot", "warm") and confidence >= .50:
                    v2_hot_warm.add(pid)

    if not prospects:
        raise ValueError("historic archive contains no prospect rows")
    pk_digest = hashlib.sha256()
    for prospect_id in sorted(prospects):
        pk_digest.update(prospect_id.encode("utf-8"))
        pk_digest.update(b"\n")
    if any(not ids <= prospects for ids in (link_prospects, acquired, qualified_any)):
        raise ValueError("archive contains references outside archived prospect cohort")

    overlap_count = None
    exchange_source_date = None
    if exchange is not None:
        if (
            exchange.get("schema_version") != "empire.commercial_exchange_snapshot.v1"
            or exchange.get("source") != "canonical_empiredb_projection"
            or exchange.get("canonical_backend") != "empiredb"
            or exchange.get("execution_authority") != "none"
            or exchange.get("actual_revenue") is not False
        ):
            raise ValueError("invalid current Commercial Exchange evidence")
        inventory = exchange.get("inventory")
        if not isinstance(inventory, list):
            raise ValueError("current exchange inventory must be a list")
        ids = {
            str(row.get("prospect_id") or "").strip()
            for row in inventory if isinstance(row, dict) and row.get("prospect_id")
        }
        overlap_count = len(prospects & ids)
        exchange_source_date = exchange.get("observed_at")
    return {
        "schema_version": "empire.tam-historical-prospect-census.v1",
        "mode": "OBSERVE",
        "source": "retained_local_empiredb_migration_archive",
        "historical_archive_last_modified_at": datetime.fromtimestamp(
            dump.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        "source_is_current_empiredb_query": False,
        "current_live_prospect_total": None,
        "archived_unique_prospects": len(prospects),
        "archived_prospect_id_sha256": pk_digest.hexdigest(),
        "archived_qualified_any_count": len(qualified_any),
        "archived_v1_qualified_count": len(v1),
        "archived_v2_qualified_count": len(v2),
        "archived_v2_hot_warm_evidence_candidates": len(v2_hot_warm),
        "archived_identity_linked_prospects": len(link_prospects),
        "archived_distinct_linked_entities": len(entity_ids),
        "archived_acquisition_linked_prospects": len(acquired),
        "archived_prospects_without_qualification": len(prospects - qualified_any),
        "archived_prospects_without_v2_qualification": len(prospects - v2),
        "archived_prospects_without_identity_link": len(prospects - link_prospects),
        "archived_missing_metro": geo_missing,
        "archived_qualification_state_rows": dict(sorted(qualified_by_state.items())),
        "archived_status_counts": dict(sorted(status.items())),
        "archived_contact_field_presence_not_verification": dict(sorted(contact_routes.items())),
        "archived_top_15_sectors": [
            {"sector": sector_name, "prospect_rows": count}
            for sector_name, count in sector.most_common(15)
        ],
        "archived_other_sector_rows": sum(sector.values()) - sum(
            count for _, count in sector.most_common(15)
        ),
        "archived_first_prospect_date": first_seen,
        "archived_last_prospect_date": last_seen,
        "current_exchange_observed_at": exchange_source_date,
        "archived_id_overlap_with_current_exchange": overlap_count,
        "not_in_current_exchange_is_unqualified": None,
        "archived_contact_fields_are_legal_outreach_authority": False,
        "archived_v2_score_is_current_qualification": False,
        "eligible_for_allocation": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--exchange", type=Path)
    args = parser.parse_args()
    saved = None
    if args.exchange:
        if args.exchange.is_symlink() or not args.exchange.is_file() or args.exchange.stat().st_size > 10_000_000:
            raise ValueError("unsafe Commercial Exchange receipt")
        saved = json.loads(args.exchange.read_text(encoding="utf-8"))
    report = inspect_archive(dump=args.dump, exchange=saved)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
