#!/usr/bin/env python3
"""Refresh evidence-backed Opportunity Factory normalized signals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.opportunity_evidence_normalizer import (
    refresh_normalized_signals,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_normalized_signals(
        Path(args.repo_root).resolve()
    )
    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "candidates_with_any_normalized_score": payload[
            "candidates_with_any_normalized_score"
        ],
        "total_normalized_scores": payload[
            "total_normalized_scores"
        ],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
