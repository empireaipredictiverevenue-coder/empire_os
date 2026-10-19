"""Offline reconciliation of bounded Scrapling business observations.

Reads TWO local JSON files prepared under independent approvals: reviewed
source evidence and a complete/consistent EmpireDB identity snapshot.
No database connection, crawler, service, outbound, provider runs, or writes.

This is NOT a canonical ingestion script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.scrapling_identity_review import review_scrapling_canonical_identity
from empire_os.waterfall_source_bridge import EvidenceReview, VERTICAL_TARGETS


def _load(path: Path, budget: int):
    if not path.is_file() or path.stat().st_size > budget:
        raise ValueError("missing_or_unbounded_input")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--canonical-identity-snapshot", type=Path, required=True)
    parser.add_argument("--snapshot-ref", required=True)
    parser.add_argument("--complete-snapshot", action="store_true")
    parser.add_argument("--vertical", required=True, choices=sorted(VERTICAL_TARGETS))
    parser.add_argument("--target-kind", required=True)
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--identity-ref", required=True)
    parser.add_argument("--jurisdiction-policy-ref", default="")
    opts = parser.parse_args(argv)
    try:
        report = _load(opts.source_report, 2_000_000)
        rows = _load(opts.canonical_identity_snapshot, 6_000_000)
        reviewed = review_scrapling_canonical_identity(
            report=report,
            review=EvidenceReview(
                vertical=opts.vertical,
                target_kind=opts.target_kind,
                jurisdiction=opts.jurisdiction,
                company_identity_ref=opts.identity_ref,
                jurisdiction_policy_ref=opts.jurisdiction_policy_ref,
            ),
            canonical_rows=rows, canonical_snapshot_complete=opts.complete_snapshot,
            canonical_snapshot_ref=opts.snapshot_ref,
        )
        print(json.dumps(reviewed, sort_keys=True))
        return 0 if all(
            item["state"] not in {"HOLD", "IDENTITY_CONFLICT", "AMBIGUOUS"}
            for item in reviewed["observation_decisions"]
        ) else 2
    except (TypeError, ValueError, OSError, UnicodeError) as exc:
        # Never expose raw source text, candidate contacts or DB details.
        print(json.dumps({
            "mode": "OFFLINE_IDENTITY_REVIEW", "state": "HOLD",
            "error_class": type(exc).__name__,
            "execution_authority": "none",
            "canonical_database_writes": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
