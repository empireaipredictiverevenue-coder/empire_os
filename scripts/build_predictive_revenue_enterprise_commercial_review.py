#!/usr/bin/env python3
"""One-shot OBSERVE review of the current enterprise research/location cohort."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from empire_os.predictive_revenue_enterprise_commercial_review import build_review
from empire_os.enterprise_domain_history_attestation import apply_operator_domain_readback
from scripts.inspect_enterprise_review_domain_history_readonly import domains_from_review

POOL = Path("runtime/predictive_revenue/enterprise_pool_latest.json")
LOCATIONS = Path("runtime/predictive_revenue/enterprise_location_enrichment_latest.json")
PROMOTION = Path("runtime/buyer_acquisition/promotion_plan_latest.json")
OUT = Path("runtime/predictive_revenue/enterprise_commercial_review_latest.json")
OPERATOR_READBACK = Path("runtime/predictive_revenue/enterprise_domain_history_operator_readback_latest.json")


def run(root: Path) -> dict:
    source_paths = (root / POOL, root / LOCATIONS, root / PROMOTION)
    if any(path.is_symlink() for path in source_paths):
        raise ValueError("UNSAFE_ENTERPRISE_REVIEW_SOURCE")
    pool, locations, promotion = [
        json.loads(path.read_text(encoding="utf-8")) for path in source_paths
    ]
    review = build_review(pool, locations, promotion)
    operator_path = root / OPERATOR_READBACK
    if operator_path.is_symlink():
        raise ValueError("UNSAFE_OPERATOR_DOMAIN_READBACK")
    if operator_path.exists():
        operator_readback = json.loads(operator_path.read_text(encoding="utf-8"))
        review = apply_operator_domain_readback(
            review, operator_readback, expected_domains=domains_from_review(review)
        )
    target = root / OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("UNSAFE_ENTERPRISE_REVIEW_OUTPUT")
    fd, temporary = tempfile.mkstemp(prefix=".enterprise_review_", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(review, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    try:
        data = run(Path(args.repo_root))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        print(json.dumps({"status": "HELD_SOURCE_OR_SNAPSHOT_INVALID", "mode": "OBSERVE",
                          "outbound_sent": False, "database_write_performed": False}))
        return 2
    print(json.dumps({"status": "REVIEW_PACKET_READY", "research_pool_count": data["research_pool_count"],
                      "location_verified_current_count": data["location_verified_current_count"],
                      "fit_review_current_count": data["fit_review_current_count"],
                      "customer_discovery_review_count": data["customer_discovery_review_count"],
                      "competitive_overlap_review_count": data["competitive_overlap_review_count"],
                      "commercially_qualified_count": data["commercially_qualified_count"],
                      "outreach_authorized": False, "database_write_performed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
