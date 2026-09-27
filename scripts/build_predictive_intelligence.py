#!/usr/bin/env python3
"""Refresh verified-cohort Predictive Intelligence."""
from __future__ import annotations

import argparse
import json

from empire_os.predictive_intelligence import (
    refresh_predictive_intelligence,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--min-terminal-samples", type=int, default=20)
    parser.add_argument("--min-timing-samples", type=int, default=8)
    args = parser.parse_args()

    payload = refresh_predictive_intelligence(
        args.repo_root,
        request=request_json,
        min_terminal_samples=max(1, args.min_terminal_samples),
        min_timing_samples=max(1, args.min_timing_samples),
    )
    field_availability = {
        "probability_success": any(
            row.get("probability_available") is True
            for row in payload.get("product_estimates", {}).values()
        ),
        "confidence": any(
            row.get("confidence") is not None
            for row in payload.get("product_estimates", {}).values()
        ),
        "uncertainty": any(
            row.get("uncertainty") is not None
            for row in payload.get("product_estimates", {}).values()
        ),
        "time_to_revenue_days": any(
            row.get("time_to_revenue_available") is True
            for row in payload.get("product_estimates", {}).values()
        ),
    }
    print(json.dumps({
        "ok": True,
        "source_outcome_count": payload["source_outcome_count"],
        "matched_outcome_count": payload["matched_outcome_count"],
        "probability_ready_product_count": payload[
            "probability_ready_product_count"
        ],
        "timing_ready_product_count": payload[
            "timing_ready_product_count"
        ],
        "field_availability": field_availability,
        "field_blockers": {
            key: (
                None
                if available
                else "insufficient_verified_outcome_cohort"
            )
            for key, available in field_availability.items()
        },
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
