#!/usr/bin/env python3
"""Own-scope agent tick: plan research, review permitted packets, write local status.

Never reads production secrets, initiates a network call or queues external action.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from empire_os.agents.meta_market_validation_agent import run_agent

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "runtime" / "meta_market_research_agent"


def _read_packet(path_str: str | None):
    if not path_str:
        return None
    path = Path(path_str).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 200_000:
        raise ValueError("invalid_or_oversized_evidence_packet")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_write(path: Path, obj: dict):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("unsafe_output_path")
    data = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    fd, tmp_path = tempfile.mkstemp(prefix=".meta_research_", dir=path.parent, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Empire Meta Market Validation Agent (OBSERVE)")
    parser.add_argument("--observations-file", help="Optional pre-authorised structured evidence packet")
    parser.add_argument("--report-only", action="store_true", help="Print result without writing local reports")
    args = parser.parse_args()
    packet = _read_packet(args.observations_file)
    result = run_agent(evidence_packet=packet)
    if not args.report_only:
        if REPORT_DIR.is_symlink():
            raise ValueError("unsafe_report_directory")
        REPORT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        _safe_write(REPORT_DIR / "latest.json", result)
        _safe_write(REPORT_DIR / "research_tasks.json", {
            "owner": result["agent"], "mode": "OBSERVE",
            "external_execution": False,
            "tasks": [t for lane in result["lanes"] for t in lane["agent_tasks"]],
        })
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
