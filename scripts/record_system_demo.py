#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.system_demo_recorder import (
    founder_console_demo_plan,
    record_demo,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8775",
    )
    parser.add_argument(
        "--output-dir",
        default="/srv/empire_os/runtime/demo_recordings",
    )
    parser.add_argument(
        "--name",
        default="empire-founder-console-demo.mp4",
    )
    args = parser.parse_args()

    plan = founder_console_demo_plan(base_url=args.base_url)
    result = record_demo(
        plan,
        output_dir=Path(args.output_dir),
        mp4_name=args.name,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
