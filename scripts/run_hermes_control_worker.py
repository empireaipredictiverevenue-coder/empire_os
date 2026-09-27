#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.hermes_control import run_worker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument(
        "--control-branch",
        default="ops/hermes-control",
    )
    parser.add_argument("--max-jobs", type=int, default=1)
    args = parser.parse_args()

    payload = run_worker(
        Path(args.repo_root).resolve(),
        control_branch=args.control_branch,
        max_jobs=args.max_jobs,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
