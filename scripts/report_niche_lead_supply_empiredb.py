#!/usr/bin/env python3
"""Build an additive private lead-supply snapshot from canonical EmpireDB.

Read-only: bounded SELECT/COUNT, no DDL, DML, crawling, email, or publication.
Requires the existing privately provisioned EMPIREDB_DSN in the process env.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.canonical_data_gateway import empiredb_gateway_from_environment
from empire_os.data_query import OrderSpec
from empire_os.lead_supply_intelligence import (
    build_lead_supply_report, crawler_receipt_summary,
)
from empire_os.lead_scoring_inventory_bridge import (
    ENGINE_REGISTER, build_scoring_coverage, cortex_runtime_summary,
)
from empire_os.lead_territory_mrr_bridge import build_territory_mrr_bridge


COLUMNS = {
    "prospects": "id,niche,metro,status",
    "prospect_acquisitions": "id,prospect_id,source",
    "prospect_qualifications": (
        "id,prospect_id,scoring_engine,scoring_version,status,tier,"
        "evidence_confidence,scored_at,entity_id,result_payload"
    ),
    "prospect_entity_links": "id,prospect_id,entity_id,active",
    "intelligence_scores": (
        "id,entity_type,entity_id,score_type,model_key,confidence,"
        "scored_at,features"
    ),
    "strike_packs": (
        "id,slug,name,tier,monthly_price_cents,price_per_lead_cents,"
        "max_leads_per_month,lane_count,niches,is_active,is_public"
    ),
    "buyer_subscriptions": (
        "id,buyer_id,pack_id,monthly_price_cents,active,status,"
        "period_start,period_end"
    ),
}


class IncompleteCanonicalRead(RuntimeError):
    pass


def read_complete_table(gateway: Any, table: str, *, page_size: int, max_rows: int):
    """Fail closed on truncated paginated scans; do not return partial totals."""
    expected = gateway.count(table)
    if expected > max_rows:
        raise IncompleteCanonicalRead(
            f"{table}: {expected} rows exceed approved read cap {max_rows}"
        )
    result: list[dict[str, Any]] = []
    for offset in range(0, expected, page_size):
        rows = gateway.query(
            table, COLUMNS[table],
            order=(OrderSpec("id"),),
            offset=offset,
            limit=min(page_size, expected - offset),
        )
        result.extend(dict(row) for row in rows)
    after = gateway.count(table)
    if len(result) != expected or after != expected:
        raise IncompleteCanonicalRead(
            f"{table}: pagination/row count changed; retry with a stable snapshot"
        )
    if len({str(row.get("id")) for row in result}) != len(result):
        raise IncompleteCanonicalRead(f"{table}: duplicate canonical IDs in page scan")
    return result


def run(
    gateway: Any,
    *,
    root: Path,
    page_size: int = 500,
    max_rows_per_table: int = 50000,
) -> dict[str, Any]:
    # Preserve lead count availability when an optional intelligence reader
    # is unavailable. Never translate missing scoring data into zero scores.
    required = ("prospects", "prospect_acquisitions", "prospect_qualifications")
    tables = {
        table: read_complete_table(
            gateway, table, page_size=page_size, max_rows=max_rows_per_table
        )
        for table in required
    }
    scoring_optional: dict[str, list[dict[str, Any]]] = {}
    scoring_reader_failure: str | None = None
    try:
        for table in ("prospect_entity_links", "intelligence_scores"):
            scoring_optional[table] = read_complete_table(
                gateway, table, page_size=page_size,
                max_rows=max_rows_per_table,
            )
    except Exception as exc:
        scoring_reader_failure = type(exc).__name__
        scoring_optional = {}
    exchange_path = root / "runtime" / "commercial_exchange" / "latest.json"
    exchange = json.loads(exchange_path.read_text())
    if (
        exchange.get("canonical_backend") != "empiredb"
        or exchange.get("source") != "canonical_empiredb_projection"
    ):
        raise ValueError("exchange snapshot is not confirmed canonical EmpireDB")
    crawl_path = root / "runtime" / "feedback" / "crawler_runs.jsonl"
    report = build_lead_supply_report(
        prospects=tables["prospects"],
        acquisitions=tables["prospect_acquisitions"],
        qualifications=tables["prospect_qualifications"],
        exchange=exchange,
        counts_complete=True,
        scanned_tables={k: len(v) for k, v in tables.items()},
        crawl_receipts=crawler_receipt_summary(crawl_path),
        observed_at=datetime.now(timezone.utc),
    )
    if scoring_optional:
        report["scoring_coverage"] = {
            "available": True,
            **build_scoring_coverage(
                prospects=tables["prospects"],
                qualifications=tables["prospect_qualifications"],
                identity_links=scoring_optional["prospect_entity_links"],
                intelligence_scores=scoring_optional["intelligence_scores"],
                cortex_snapshot=cortex_runtime_summary(
                    root / "runtime/cortex_learning/cortex_learning_latest.json"
                ),
            ),
        }
        report["table_rows_scanned"].update({
            key: len(rows) for key, rows in scoring_optional.items()
        })
    else:
        report["scoring_coverage"] = {
            "available": False,
            "engine_registry": [dict(item) for item in ENGINE_REGISTER],
            "reason": "optional_empiredb_scoring_reader_unavailable",
            "error_class": scoring_reader_failure,
            "no_scores_does_not_mean_zero": True,
            "cortex": cortex_runtime_summary(
                root / "runtime/cortex_learning/cortex_learning_latest.json"
            ),
        }
    optional_package_rows: dict[str, list[dict[str, Any]]] = {}
    package_reader_errors: dict[str, str] = {}
    for table in ("strike_packs", "buyer_subscriptions"):
        try:
            optional_package_rows[table] = read_complete_table(
                gateway, table, page_size=page_size,
                max_rows=max_rows_per_table,
            )
        except Exception as exc:
            package_reader_errors[table] = type(exc).__name__
    report["territory_mrr"] = build_territory_mrr_bridge(
        exchange=exchange,
        strike_packs=optional_package_rows.get("strike_packs"),
        buyer_subscriptions=optional_package_rows.get("buyer_subscriptions"),
        strike_packs_reader_available="strike_packs" in optional_package_rows,
        subscriptions_reader_available="buyer_subscriptions" in optional_package_rows,
    )
    report["territory_mrr"]["optional_reader_error_classes"] = package_reader_errors
    report["table_rows_scanned"].update({
        name: len(rows) for name, rows in optional_package_rows.items()
    })
    # Pagination is complete but not a transactionally consistent snapshot.
    report["transactionally_consistent_snapshot_proven"] = False
    report["limitations"] = [
        "Paginated read was not one repeatable-read DB transaction; ingestion may race the scan",
        "Acquisition source counts overlap where the same prospect has multiple sources",
        "Crawler log counts are historical events, never unique or available leads",
        "Exchange inventory contains only selected qualification records",
    ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--max-rows-per-table", type=int, default=50000)
    parser.add_argument(
        "--output", default="runtime/lead_supply/niche_counts_latest.json"
    )
    args = parser.parse_args()
    if not 1 <= args.page_size <= 1000:
        parser.error("page size must be between 1 and 1000")
    if not 1 <= args.max_rows_per_table <= 100000:
        parser.error("max rows per table must be between 1 and 100000")
    target = Path(args.repo_root).resolve() / args.output
    allowed = (Path(args.repo_root).resolve() / "runtime" / "lead_supply").resolve()
    if not target.resolve().is_relative_to(allowed) or target.suffix != ".json":
        parser.error("output must be a JSON file inside runtime/lead_supply")
    gateway = empiredb_gateway_from_environment()
    report = run(
        gateway, root=Path(args.repo_root),
        page_size=args.page_size,
        max_rows_per_table=args.max_rows_per_table,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    temp.replace(target)
    print(json.dumps({
        "status": "PRIVATE_READ_ONLY_NICHE_COUNTS_WRITTEN",
        "output": str(target),
        "unique_prospects_observed": report["unique_prospects_observed"],
        "niche_count": len(report["niches"]),
        "lead_counts_complete": report["lead_counts_complete"],
        "verified_active_buyer_seat_records": report["exchange"]["buyer_seat_states"].get("active_capacity", 0),
        "scoring_coverage_available": report["scoring_coverage"]["available"],
        "territory_mrr_catalog_count": report["territory_mrr"]["product_catalog_count"],
        "subscription_reader_available": report["territory_mrr"]["buyer_subscriptions_reader_available"],
        "execution_authority": "none",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
