#!/usr/bin/env python3
"""Optional evidence-only step inside the original 15-minute buyer Gmail cycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.heat_pump_relationship_lifecycle import run_existing_buyer_team_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", required=True)
    args = parser.parse_args()
    result = run_existing_buyer_team_review(Path("/srv/empire_os"))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "RELATIONSHIP_REVIEW_EVIDENCE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
