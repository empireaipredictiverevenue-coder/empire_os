#!/usr/bin/env python3
"""Refresh deterministic Quant review for Opportunity Factory candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.opportunity_quant_review import refresh_quant_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    payload = refresh_quant_review(Path(args.repo_root).resolve())
    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "available_decision_packet_count": payload[
            "available_decision_packet_count"
        ],
        "unavailable_decision_packet_count": payload[
            "unavailable_decision_packet_count"
        ],
        "missing_field_counts": payload["missing_field_counts"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
