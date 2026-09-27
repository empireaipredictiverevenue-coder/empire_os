#!/usr/bin/env python3
"""Run bounded Opportunity Radar public research."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.opportunity_research import refresh_opportunity_research


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_opportunity_research(
        Path(args.repo_root).resolve()
    )
    print(json.dumps({
        "ok": True,
        "researched_candidate_count": payload[
            "researched_candidate_count"
        ],
        "observation_count": payload["observation_count"],
        "error_count": payload["error_count"],
        "next_layer": payload["next_layer"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
