#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.call_manager import build_call_work, write_call_work_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=25)
    args = parser.parse_args()
    result = build_call_work(limit=args.limit)
    write_call_work_snapshot(result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
