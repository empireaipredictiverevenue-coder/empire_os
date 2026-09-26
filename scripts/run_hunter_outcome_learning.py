from __future__ import annotations

import argparse
import json

from empire_os.hunter.outcome_worker import HunterOutcomeWorker


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Empire Hunter verified outcome learning"
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--write",
        action="store_true",
        help="materialize verified outcome evidence internally",
    )
    args = parser.parse_args()

    result = HunterOutcomeWorker().run(
        limit=args.limit,
        write_authorized=args.write,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
