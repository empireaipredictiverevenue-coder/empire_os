#!/usr/bin/env python3
"""Refresh Phase 3F engineering closeout status."""
from __future__ import annotations

import argparse
import json

from empire_os.phase_3f_closeout import refresh_phase_3f_closeout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_phase_3f_closeout(args.repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("engineering_ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
