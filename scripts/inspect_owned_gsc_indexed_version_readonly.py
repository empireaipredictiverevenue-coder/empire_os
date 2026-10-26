#!/usr/bin/env python3
"""Owner-run, one-shot, five-page GSC indexed-version inspection.

Never activates indexing, public routing, crawlers, posts to EmpireDB, or
writes outside an exclusive private report. Requires preexisting service
account permissions and the existing activation gate to be set.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

from empire_os.search_intelligence.search_console import (
    configured_search_console_adapter,
)
from empire_os.search_intelligence.owned_url_inspection import inspect_fixed_urls

ROOT = Path("/var/tmp")
REPORT_NAME = re.compile(r"empire_gsc_index_inspection_20\d{6}\.json")


def write_private_once(packet: dict, output: Path, *, root: Path = ROOT) -> None:
    if (
        output.is_symlink()
        or output.parent.resolve() != root.resolve()
        or not REPORT_NAME.fullmatch(output.name)
    ):
        raise ValueError("private_report_path_required")
    fd = os.open(
        output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(packet, file, sort_keys=True, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-only", required=True, action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        packet = inspect_fixed_urls(configured_search_console_adapter())
        write_private_once(packet, args.output)
    except Exception as exc:
        # Deliberately no provider exception message, raw payloads or credentials.
        print(json.dumps({
            "status": "EVIDENCE_HOLD",
            "reason_code": type(exc).__name__,
            "website_changed": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": packet["status"], "count": packet["count"],
        "private_receipt": str(args.output),
        "google_live_test_performed": False,
        "google_indexing_request_sent": False,
        "execution_authority": "none",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
