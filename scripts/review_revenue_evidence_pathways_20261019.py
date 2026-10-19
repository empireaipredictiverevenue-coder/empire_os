#!/usr/bin/env python3
"""Read-only EmpireOS evidence-brain pathway inspection.

Uses four canonical OBSERVE snapshots. No LLM, network, source refresh,
database mutation, ASTRA dispatch, buyer activation or payments.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from empire_os.revenue_evidence_pathways import review_evidence_pathways_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Scientific Predictive Revenue pathway review")
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.top <= 10:
        parser.error("--top must be 1 to 10")
    report = review_evidence_pathways_runtime(
        Path("/srv/empire_os"),
        as_of=datetime.now(timezone.utc), limit=args.top,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "EVIDENCE_PATHWAY_REVIEW_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
