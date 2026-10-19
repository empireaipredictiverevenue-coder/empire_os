#!/usr/bin/env python3
"""Read-only flagship vendor readiness and optional offline scientific review.

Does not install packages, fork repositories, start tracking, export traces,
open a browser, record sessions, send CRM records or schedule work.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.flagship_quality_integrations import (
    flagship_vendor_readiness, run_offline_evidently_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Flagship research/UX vendor readiness")
    parser.add_argument(
        "--offline-current-aggregate", type=Path,
        help="Private local JSON with fixed OBSERVED,HELD,MISSING,STALE,UNKNOWN counts",
    )
    parser.add_argument(
        "--offline-reference-aggregate", type=Path,
        help="Private local historic JSON with matching fixed-category counts",
    )
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    result = {"vendor_integrations": flagship_vendor_readiness(as_of=now)}
    if bool(args.offline_current_aggregate) != bool(args.offline_reference_aggregate):
        parser.error("two explicitly supplied offline aggregate paths are required")
    if args.offline_current_aggregate:
        root = Path(__file__).resolve().parents[1]
        # Do not let the external research CLI read arbitrary service files
        # or accept extra structured payloads containing private identities.
        def load(path: Path) -> dict[str, int]:
            target = (root / path).resolve()
            private = (root / "runtime" / "scientific_evaluation").resolve()
            if (not target.is_relative_to(private) or
                    not target.is_file() or target.is_symlink() or
                    target.stat().st_size > 4096):
                raise ValueError("offline quality source must be a small private aggregate")
            doc = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("private aggregate data must be an object")
            return doc
        try:
            current = load(args.offline_current_aggregate)
            reference = load(args.offline_reference_aggregate)
            result["quality_evaluation"] = run_offline_evidently_report(
                reference, current, as_of=now,
            )
        except (OSError, ValueError, TypeError, UnicodeError):
            result["quality_evaluation"] = {
                "status": "UNTRUSTED_OFFLINE_REFERENCE_OR_CURRENT_AGGREGATE",
                "raw_private_data_exported": False,
                "evidently_drift_test_executed": False,
                "execution_authority": "none",
            }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
