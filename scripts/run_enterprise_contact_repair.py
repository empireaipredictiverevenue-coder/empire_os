#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from empire_os.enterprise_contact_repair import (
    record_incident,
    run_repair_cycle,
)


ROOT = Path("/srv/empire_os")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-test-log")
    parser.add_argument("--kind", default="test_failure")
    parser.add_argument("--command", default="")
    parser.add_argument("--returncode", type=int, default=1)
    args = parser.parse_args()

    if args.record_test_log:
        log = Path(args.record_test_log).read_text(
            encoding="utf-8",
            errors="replace",
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        payload = record_incident(
            kind=args.kind,
            log_text=log,
            command=args.command or "pytest",
            returncode=args.returncode,
            base_head=head,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    result = run_repair_cycle()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] not in {
        "RUNTIME_RETRY_EXHAUSTED",
        "OBSERVE_ONLY_UNKNOWN",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
