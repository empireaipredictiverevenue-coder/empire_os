"""Founder-only lead supply observatory.

An observational projection: never sends messages, seats buyers, allocates leads,
modifies financial state, or treats crawler attempts as owned lead inventory.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from empire_os.niche_taxonomy import niche_family, metro_key
from empire_os.buyer_allocation import qualification_decision
from empire_os.source_intelligence import SOURCES


SOURCE_EDGES = (
    ("lead_sources/crawler_runner", "prospect_acquisitions", "implemented_ingest"),
    ("prospect_acquisitions", "prospects", "canonical_identity"),
    ("prospects", "prospect_qualifications", "score_v2_evidence_required"),
    ("prospects", "prospect_entity_links", "identity_evidence_required"),
    ("prospect_qualifications", "commercial_exchange", "bounded_qualified_selection"),
    ("buyers", "commercial_exchange", "verified_capacity_required"),
    ("commercial_exchange", "self_serve", "interest_only_not_live_inventory"),
    ("search_intelligence", "lead_supply", "not_verified_connected"),
    ("predictive_cloud", "lead_supply", "not_verified_connected"),
    ("buyer_demand_graph", "lead_supply", "not_verified_connected"),
    ("economic_memory", "lead_supply", "not_verified_connected"),
)


def _market(value: Any, *, niche: bool) -> str:
    result = niche_family(value) if niche else metro_key(value)
    return result or "unclassified"


def crawler_receipt_summary(path: Path, *, max_lines: int = 250_000) -> dict[str, Any]:
    """Log events are attempts/observations, not unique EmpireDB leads."""
    wanted = {
        "source_run_start", "source_run_done", "crawler_run_start",
        "crawler_run_done", "prospect_acquired", "prospect_matched",
        "canonical_ingest_failed", "source_crashed", "candidate",
    }
    totals: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    lines = 0
    malformed = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                lines += 1
                if lines > max_lines:
                    break
                try:
                    event = json.loads(line)
                except (ValueError, TypeError):
                    malformed += 1
                    continue
                if not isinstance(event, dict):
                    malformed += 1
                    continue
                kind = str(event.get("msg") or "")
                if kind not in wanted:
                    continue
                totals[kind] += 1
                source = str(event.get("source") or "unspecified")
                by_source[source][kind] += 1
    except OSError:
        return {"available": False, "events_are_not_unique_leads": True}
    return {
        "available": True,
        "record_count": min(lines, max_lines),
        "truncated": lines > max_lines,
        "malformed_rows": malformed,
        "event_totals": dict(sorted(totals.items())),
        "by_source": {k: dict(sorted(v.items())) for k, v in sorted(by_source.items())},
        "events_are_not_unique_leads": True,
    }


def build_lead_supply_report(
    *,
    prospects: Iterable[Mapping[str, Any]],
    acquisitions: Iterable[Mapping[str, Any]],
    qualifications: Iterable[Mapping[str, Any]],
    exchange: Mapping[str, Any],
    counts_complete: bool,
    scanned_tables: Mapping[str, int],
    crawl_receipts: Mapping[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Counts unique canonical prospect IDs per niche and metro.

    Sources use acquisition ledger evidence and can overlap across sources.
    Exchange seats and inventory remain bounded projections, not total inventory.
    """
    ids: dict[str, dict[str, Any]] = {}
    for row in prospects:
        identity = str(row.get("id") or "").strip()
        if identity:
            ids[identity] = {
                "niche": _market(row.get("niche"), niche=True),
                "metro": _market(row.get("metro"), niche=False),
                "status": str(row.get("status") or "unknown"),
            }

    sources_by_id: dict[str, set[str]] = defaultdict(set)
    acquisition_events = 0
    for row in acquisitions:
        identity = str(row.get("prospect_id") or "").strip()
        if identity in ids:
            acquisition_events += 1
            sources_by_id[identity].add(str(row.get("source") or "unknown").strip() or "unknown")

    chosen: dict[str, dict[str, Any]] = {}
    for row in qualifications:
        pid = str(row.get("prospect_id") or "").strip()
        if pid not in ids:
            continue
        if str(row.get("scoring_engine") or "") != "empire_os.lead_scoring":
            continue
        version = str(row.get("scoring_version") or "")
        if version not in {"v1", "v2"}:
            continue
        prior = chosen.get(pid)
        if prior is None or (prior.get("scoring_version") == "v1" and version == "v2"):
            chosen[pid] = dict(row)

    qualified_ids = {pid for pid, row in chosen.items() if qualification_decision(row)[0]}
    by_niche: dict[str, dict[str, Any]] = {}
    by_corridor: Counter[tuple[str, str]] = Counter()
    source_totals: dict[str, set[str]] = defaultdict(set)
    for pid, info in ids.items():
        n, m = info["niche"], info["metro"]
        item = by_niche.setdefault(n, {
            "niche": n, "unique_leads_observed": 0,
            "qualified_with_evidence_observed": 0,
            "no_acquisition_provenance": 0,
            "by_metro": {}, "by_status": {}, "by_source": {},
        })
        item["unique_leads_observed"] += 1
        item["by_metro"][m] = item["by_metro"].get(m, 0) + 1
        item["by_status"][info["status"]] = item["by_status"].get(info["status"], 0) + 1
        by_corridor[(n, m)] += 1
        if pid in qualified_ids:
            item["qualified_with_evidence_observed"] += 1
        if not sources_by_id.get(pid):
            item["no_acquisition_provenance"] += 1
        for source in sources_by_id.get(pid, ()):
            item["by_source"][source] = item["by_source"].get(source, 0) + 1
            source_totals[source].add(pid)

    seat_states = Counter(
        str(s.get("seat_state") or "unknown") for s in exchange.get("buyer_seats", [])
    )
    seat_by_niche: dict[str, Counter[str]] = defaultdict(Counter)
    for seat in exchange.get("buyer_seats", []):
        seat_by_niche[_market(seat.get("niche_family"), niche=True)][
            str(seat.get("seat_state") or "unknown")
        ] += 1
    sample_by_niche: dict[str, Counter[str]] = defaultdict(Counter)
    for item in exchange.get("inventory", []):
        sample_by_niche[_market(item.get("niche_family"), niche=True)][
            str(item.get("state") or "unknown")
        ] += 1

    corridor_stats: dict[str, dict[str, Any]] = {}
    for side, rows in (
        ("seat", exchange.get("buyer_seats", [])),
        ("supply", exchange.get("inventory", [])),
    ):
        for item in rows:
            key = str(item.get("corridor_key") or "").strip()
            if not key:
                continue
            record = corridor_stats.setdefault(key, {
                "corridor_key": key,
                "niche": _market(item.get("niche_family"), niche=True),
                "metro": _market(item.get("metro"), niche=False),
                "buyer_seat_records": 0,
                "active_seat_records": 0,
                "blocked_seat_records": 0,
                "sampled_supply": 0,
                "sampled_overflow": 0,
                "sampled_allocation_ready": 0,
            })
            if side == "seat":
                record["buyer_seat_records"] += 1
                record["active_seat_records"] += (
                    str(item.get("seat_state")) == "active_capacity"
                )
                record["blocked_seat_records"] += (
                    str(item.get("seat_state")) == "blocked_missing_evidence"
                )
            else:
                record["sampled_supply"] += 1
                record["sampled_overflow"] += (
                    str(item.get("state")) == "overflow_no_capacity"
                )
                record["sampled_allocation_ready"] += (
                    str(item.get("state")) == "allocation_candidate"
                )

    for niche, record in by_niche.items():
        record["exchange_sample_states"] = dict(sorted(sample_by_niche[niche].items()))
        record["buyer_seat_states"] = dict(sorted(seat_by_niche[niche].items()))
        for field in ("by_metro", "by_status", "by_source"):
            record[field] = dict(sorted(record[field].items()))

    timestamp = observed_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("observed_at must be timezone aware")
    return {
        "schema_version": "empire.lead_supply_intelligence.v1",
        "mode": "OBSERVE",
        "canonical_backend": "empiredb",
        "observed_at": timestamp.astimezone(timezone.utc).isoformat(),
        "lead_counts_complete": bool(counts_complete),
        "incomplete_counts_must_not_be_presented_as_totals": not counts_complete,
        "source": "canonical_empiredb_read_only",
        "unique_prospects_observed": len(ids),
        "qualified_with_evidence_observed": len(qualified_ids),
        "acquisition_events_for_scanned_prospects": acquisition_events,
        "prospects_missing_acquisition_provenance": sum(
            not sources_by_id.get(pid) for pid in ids
        ),
        "source_unique_prospect_counts_overlap": True,
        "source_unique_prospect_counts": {
            k: len(v) for k, v in sorted(source_totals.items())
        },
        "table_rows_scanned": dict(sorted(scanned_tables.items())),
        "niches": sorted(by_niche.values(), key=lambda x: (-x["unique_leads_observed"], x["niche"])),
        "niche_metro_counts": [
            {"niche": n, "metro": m, "unique_leads_observed": count}
            for (n, m), count in sorted(by_corridor.items())
        ],
        "exchange": {
            "observed_at": exchange.get("observed_at"),
            "population": "qualified_selected_sample_not_full_prospect_universe",
            "inventory_sample_count": exchange.get("inventory_count"),
            "buyer_seat_record_count": len(exchange.get("buyer_seats", [])),
            "buyer_seat_states": dict(sorted(seat_states.items())),
            "corridor_count": exchange.get("corridor_count"),
            "verified_market_price_count": exchange.get("verified_market_price_count"),
            "allocation_candidate_count": exchange.get("allocation_candidate_count"),
            "no_active_seat_inference_from_record_count": True,
        },
        "corridors": sorted(
            corridor_stats.values(),
            key=lambda row: (row["niche"], row["metro"], row["corridor_key"]),
        ),
        "corridor_supply_is_qualified_sample_only": True,
        "crawler_receipts": dict(crawl_receipts or {"available": False}),
        "source_contract_catalog": [
            {
                "source_id": source.source_id,
                "country": source.country_code,
                "niches": list(source.niches),
                "production_status_in_catalog": source.production_status,
                "licence": source.licence,
                "raw_resale_allowed": source.raw_resale_allowed,
                "allowed_uses": list(source.allowed_uses),
                "live_credential_and_run_status_verified": False,
            }
            for source in sorted(SOURCES.values(), key=lambda source: source.source_id)
        ],
        "source_contract_catalog_is_not_live_connection_proof": True,
        "intelligence_connections": [
            {"from": start, "to": end, "state": state}
            for start, end, state in SOURCE_EDGES
        ],
        "public_self_serve_raw_lead_counts_allowed": False,
        "lead_sale_authorized": False,
        "buyer_seating_authorized": False,
        "crawling_triggered": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }
