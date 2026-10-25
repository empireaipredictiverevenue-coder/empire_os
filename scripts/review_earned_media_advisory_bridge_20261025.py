#!/usr/bin/env python3
"""Founder review of existing PR, editorial, consultancy and proposal evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.earned_media_advisory_bridge import review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-only", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pr-root", type=Path,
                        help="Explicit path to existing PR/consultancy branch/worktree")
    parser.add_argument("--distribution-root", type=Path,
                        help="Explicit path to canonical existing Revenue Distribution snapshot")
    parser.add_argument("--with-leadgen", action="store_true",
                        help="Add bounded original B2B demand and research account priority review")
    args = parser.parse_args(argv)
    packet = review(args.repo_root, pr_root=args.pr_root,
                    distribution_root=args.distribution_root)
    if args.with_leadgen:
        from empire_os.earned_media_leadgen_review import review_lead_generation
        packet["lead_generation"] = review_lead_generation(
            packet, repo_root=args.repo_root,
            distribution_root=args.distribution_root or args.repo_root,
        )
    print(json.dumps(packet, sort_keys=True))
    return 2 if packet["status"].endswith("SOURCE_GAPS") else 0


if __name__ == "__main__":
    raise SystemExit(main())
