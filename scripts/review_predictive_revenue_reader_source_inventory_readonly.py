#!/usr/bin/env python3
"""Print repository-only proof inventory for the existing EmpireDB event reader.

No DB connection, financial records, role grants, credentials, or source writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.finance_event_reader_source_contract import review_source


def main(argv=None, *, root: Path = Path("/srv/empire_os")) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status": "HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    evidence = review_source(root)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
