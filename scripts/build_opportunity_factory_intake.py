#!/usr/bin/env python3
"""Refresh truth-preserving Opportunity Factory intake readiness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.opportunity_factory_intake import refresh_factory_intake


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    payload = refresh_factory_intake(Path(args.repo_root).resolve())
    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "factory_ready_count": payload["factory_ready_count"],
        "blocked_count": payload["blocked_count"],
        "candidates_with_any_normalized_score": payload[
            "candidates_with_any_normalized_score"
        ],
        "candidates_with_both_buyer_intent_and_demand_values": payload[
            "candidates_with_both_buyer_intent_and_demand_values"
        ],
        "candidate_evidence_gap_counts": payload["candidate_evidence_gap_counts"],
        "unverified_buyer_demand_not_negative_evidence": True,
        "search_observation_scores_inferred": payload[
            "search_observation_scores_inferred"
        ],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
