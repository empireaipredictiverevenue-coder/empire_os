"""Founder/private read-only summary: canonical Exchange + source sweep pool.

No raw company rows, contact data, emails or buyer IDs. A sweep cannot add to
Exchange inventory without existing governed canonical ingest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory

MAX_FILE_BYTES = 5_000_000


def _load(path: Path):
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("private_evidence_snapshot_missing_or_unbounded")
    return json.loads(path.read_text(encoding="utf-8"))


def compare_private_inventory(
    *,
    exchange: dict,
    source_sweep: dict,
    now: datetime | None = None,
) -> dict:
    inventory = build_lead_exchange_live_inventory(exchange, now=now)
    if inventory["state"] == "HOLD":
        raise ValueError("canonical_exchange_contract_hold")
    if (
        not isinstance(source_sweep, dict)
        or source_sweep.get("schema_version") != "empire.recc_solar_supply_sweep.v1"
        or source_sweep.get("source_id") != "gb_recc_solar"
        or source_sweep.get("state") not in ("COMPLETED", "COMPLETED_WITH_SOURCE_ERRORS")
        or source_sweep.get("canonical_empiredb_writes") is not False
        or source_sweep.get("outbound_authorized") is not False
    ):
        raise ValueError("private_source_sweep_contract_hold")
    research_count = source_sweep.get("unique_research_observations")
    added = source_sweep.get("commercial_exchange_inventory_added")
    if type(research_count) is not int or not 0 <= research_count <= 40 or added != 0:
        raise ValueError("source_sweep_must_not_claim_canonical_stock")
    return {
        "schema_version": "empire.supply_sweep_exchange_comparison.v1",
        "mode": "READ_ONLY_PRIVATE_INVENTORY",
        "as_of": (now or datetime.now(timezone.utc)).isoformat(),
        "exchange_observed_at": inventory["observed_at"],
        "canonical_exchange_selected_inventory": inventory["selected_inventory_records"],
        "canonical_exchange_evidence_holds": inventory["evidence_hold_records"],
        "canonical_exchange_capacity_waitlist": inventory["buyer_capacity_waitlist_records"],
        "canonical_exchange_allocation_candidates": inventory["allocation_candidate_records"],
        "canonical_exchange_delivery_ready": 0,
        "registered_source_id": source_sweep["source_id"],
        "research_sweep_observed_at": source_sweep["observed_at"],
        "distinct_private_source_research_observations": research_count,
        "research_not_yet_in_verified_exchange": True,
        "increment_to_exchange_from_sweep": 0,
        "next_step": "run canonical identity and source-rights verification before separately approved EmpireDB ingestion",
        "public_inventory_claim_allowed": False,
        "outbound_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--exchange", type=Path, required=True)
    parser.add_argument("--sweep", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = compare_private_inventory(
            exchange=_load(args.exchange),
            source_sweep=_load(args.sweep),
        )
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        result = {
            "schema_version": "empire.supply_sweep_exchange_comparison.v1",
            "state": "HOLD",
            "reason": type(exc).__name__,
            "canonical_empiredb_writes": False,
            "execution_authority": "none",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("mode") == "READ_ONLY_PRIVATE_INVENTORY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
