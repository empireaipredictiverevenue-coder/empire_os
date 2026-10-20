#!/usr/bin/env python3
"""Offline JSON review: never retrieves Meta pages or writes to a database."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.meta_social_opportunity_research import review_packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Meta social opportunity research, offline / observe-only")
    parser.add_argument("--observations-file", required=True, help="Pre-authorised structured observations JSON")
    args = parser.parse_args()
    path = Path(args.observations_file).resolve()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 200_000:
        raise ValueError("invalid_or_oversized_offline_packet")
    packet = json.loads(path.read_text(encoding="utf-8"))
    result = review_packet(packet)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
