#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from empire_os.founder_directives import FounderDirectiveStore

ROOT = Path("/srv/empire_os")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text")
    parser.add_argument("--title")
    parser.add_argument("--source", default="founder")
    parser.add_argument("--priority", type=int, default=90)
    args = parser.parse_args()

    text = args.text
    if not text:
        text = sys.stdin.read()
    store = FounderDirectiveStore(ROOT)
    directive, created = store.ingest(
        text,
        source=args.source,
        title=args.title,
        priority=args.priority,
    )
    print(json.dumps({
        "ok": True,
        "created": created,
        "directive": directive.as_dict(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
