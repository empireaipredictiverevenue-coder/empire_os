#!/usr/bin/env python3
"""Refresh the Predictive Cloud Opportunity Radar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.opportunity_radar import refresh_opportunity_radar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    payload = refresh_opportunity_radar(Path(args.repo_root).resolve())
    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "factory_ready_count": payload["factory_ready_count"],
        "source_status": payload["source_status"],
        "automatic_research_allowed": payload[
            "automatic_research_allowed"
        ],
        "automatic_external_execution_allowed": payload[
            "automatic_external_execution_allowed"
        ],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
