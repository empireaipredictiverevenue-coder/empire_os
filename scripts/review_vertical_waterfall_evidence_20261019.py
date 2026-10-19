"""Operator-only offline preview of the Empire-owned Waterfall source bridge.

Usage (from checked-out feature worktree):
 python -m scripts.review_vertical_waterfall_evidence_20261019 --read-only \
  --report /tmp/reviewed_fixture.json --vertical solar --target-kind contractor \
  --jurisdiction GB-ENG --company-identity-ref entity:reviewed-123

Does NOT execute a provider, invoke a service, mutate EmpireDB or contact anyone.
Provided receipts are claims supplied by the operator, not independently proven.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from empire_os.waterfall_source_bridge import (
    EvidenceReview, VERTICAL_TARGETS, build_waterfall_source_review,
)

MAX_REPORT_BYTES = 2_000_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--record-index", type=int, default=0)
    parser.add_argument("--vertical", required=True, choices=sorted(VERTICAL_TARGETS))
    parser.add_argument("--target-kind", required=True)
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--company-identity-ref", default="")
    parser.add_argument("--jurisdiction-policy-ref", default="")
    parser.add_argument("--verified-first-party-website", default="")
    parser.add_argument("--website-verification-ref", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.report.is_file():
            raise ValueError("offline report file does not exist")
        if args.report.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("report exceeds offline size limit")
        source_report = json.loads(args.report.read_text(encoding="utf-8"))
        result = build_waterfall_source_review(
            source_report,
            record_index=args.record_index,
            review=EvidenceReview(
                vertical=args.vertical, target_kind=args.target_kind,
                jurisdiction=args.jurisdiction,
                company_identity_ref=args.company_identity_ref,
                jurisdiction_policy_ref=args.jurisdiction_policy_ref,
                verified_first_party_website=args.verified_first_party_website,
                website_verification_ref=args.website_verification_ref,
            )
        )
    except (ValueError, TypeError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Never echo source text, file content, prospective contact details or
        # operator-provided evidence in error messages.
        print(json.dumps({
            "status": "HOLD", "reason": type(exc).__name__,
            "mode": "OFFLINE_REVIEW_ONLY", "execution_authority": "none",
        }))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "EVIDENCE_REVIEW_READY" else 2


if __name__ == "__main__":
    sys.exit(main())
