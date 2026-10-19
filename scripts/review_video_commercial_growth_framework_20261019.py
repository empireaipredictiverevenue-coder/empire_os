#!/usr/bin/env python3
"""Manual read-only review of local JSON packets; no live DB/network access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping

from empire_os.video_commercial_growth_framework import build_commercial_growth_review


def read_packet(filename: str) -> Mapping:
    path = Path(filename).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 3_000_000:
        raise ValueError("each input must be a JSON file no larger than 3 MB")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline, read-only Empire AI commercial framework research")
    parser.add_argument("--observations-file", required=True)
    parser.add_argument("--offer-book-file", required=True)
    parser.add_argument("--funnel-file", required=True)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    report = build_commercial_growth_review(
        observations=read_packet(args.observations_file),
        offer_book=read_packet(args.offer_book_file),
        funnel=read_packet(args.funnel_file),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
