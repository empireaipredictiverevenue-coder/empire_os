#!/usr/bin/env python3
"""Inspect real public-business research domains mined from owner snapshots.

Informational only: company domain presence is not buyer identity, city-level
activity, consent or purchase intent. Never dispatches or enriches via network.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from empire_os.a2a_b2b_evidence_mining_v1 import SCHEMA

SOURCE = (Path(__file__).resolve().parents[1] /
          "runtime/a2a_commercial_signal_mining/targeted_business_evidence_mining_v1.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review bounded B2B data mining output")
    parser.add_argument("--market", required=True, choices=("tampa, fl", "little rock, ar", "nyc"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 30:
        raise ValueError("REVIEW_RESULT_LIMIT_REQUIRED")
    if SOURCE.is_symlink() or not SOURCE.is_file() or SOURCE.stat().st_size > 200_000:
        raise ValueError("MINING_REPORT_MISSING_OR_UNSAFE")
    data = json.loads(SOURCE.read_text(encoding="utf8"))
    if (not isinstance(data, dict)
            or data.get("schema_version") != SCHEMA
            or data.get("mode") != "OBSERVE"
            or data.get("execution_authority") != "NONE"
            or data.get("verified_real_lead_count") != 0
            or data.get("crm_write_performed") is not False
            or data.get("outbound_messages") != 0):
        raise ValueError("UNTRUSTED_MINING_OUTPUT")
    rows = data.get("target_mining_results")
    if not isinstance(rows, list) or len(rows) > 10:
        raise ValueError("INVALID_MINING_TARGETS")
    matched = [r for r in rows if isinstance(r, dict) and r.get("requested_metro") == args.market]
    if len(matched) != 1:
        raise ValueError("MINING_TARGET_NOT_PRESENT")
    row = matched[0]
    if not isinstance(row.get("records"), list):
        raise ValueError("INVALID_MINING_RESEARCH_ROWS")
    print(json.dumps({
        "schema_version": "empire.a2a.public_b2b_domain_review.v1",
        "mode": "OBSERVE", "execution_authority": "NONE",
        "requested_market": args.market, "sector": row["niche"],
        "total_sector_related_research_domains": row["public_business_research_record_count"],
        "public_domains_for_existing_buyer_scout_owner_review": row["records"][:args.limit],
        "county_city_target_verified": False,
        "buyers_independently_verified": 0,
        "lead_contacts_created": 0,
        "network_requests_performed": 0,
        "messages_sent": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
