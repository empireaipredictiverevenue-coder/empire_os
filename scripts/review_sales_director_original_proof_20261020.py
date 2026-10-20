#!/usr/bin/env python3
"""Original inbound proof handoff for existing Sales Director, read-only only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_sales_director_original_proof import (
    review_sales_director_original_proof,
)
from empire_os.conversation_control_operational_truth import inspect_conversation_evidence
from scripts.review_commercial_conversation_casebook_20261020 import build_casebook_runtime


def build_original_proof_runtime(
    root: Path, *, now: datetime, conversation_proof: dict | None = None,
):
    """Reuse existing owner evidence; avoid duplicate observer work when supplied."""
    book = build_casebook_runtime(root, now=now)
    truth = (
        conversation_proof if conversation_proof is not None
        else inspect_conversation_evidence(root, now=now)
    )
    return review_sales_director_original_proof(
        casebook=book, conversation_proof=truth, now=now,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exact historical threads vs existing original Conversation OS evidence"
    )
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve(strict=True)
    result = build_original_proof_runtime(root, now=datetime.now(timezone.utc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
