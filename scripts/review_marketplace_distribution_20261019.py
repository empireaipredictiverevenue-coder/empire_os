"""Read-only marketplace/publisher revenue-channel research.

No accounts created, outreach sent, paid calls, CRM writes, or product
listings published. Requires existing owner research for dedup.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.marketplace_distribution_research_20261019 import (
    review_marketplace_distribution,
)

DEFAULT_SWEEP = Path(
    "/srv/empire_os/runtime/buyer_network_intelligence/"
    "fresh_publisher_network_sweep_20261019_review.json")
DEFAULT_RELATIONSHIPS = Path(
    "/srv/empire_os/runtime/buyer_network_intelligence/"
    "commercial_relationship_registry_latest.json")


def _read_private_snapshot(path: Path) -> dict:
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= 2_500_000):
        raise ValueError("source_snapshot_unavailable_or_untrusted")
    with path.open("r", encoding="utf-8") as handle:
        obj = json.load(handle)
    if not isinstance(obj, dict):
        raise ValueError("source_snapshot_shape_invalid")
    return obj


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--owner-sweep", type=Path, default=DEFAULT_SWEEP)
    parser.add_argument("--relationship-registry", type=Path, default=DEFAULT_RELATIONSHIPS)
    args=parser.parse_args(argv)
    try:
        result=review_marketplace_distribution(
            _read_private_snapshot(args.relationship_registry),
            _read_private_snapshot(args.owner_sweep),
            at=datetime.now(timezone.utc),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        print(json.dumps({
            "schema_version":"empire.marketplace_distribution_research.v1",
            "state":"HOLD_SOURCE_CONTRACT_OR_MISSING_RESEARCH",
            "applications_submitted":0,
            "outbound_authorized":False,
            "canonical_empiredb_writes":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
