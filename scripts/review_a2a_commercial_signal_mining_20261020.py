#!/usr/bin/env python3
"""Run a bounded, read-only A2A research tick against existing EmpireOS snapshots.

A local report is output only if --write-local is requested. No external calls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from empire_os.a2a_commercial_signal_miner import agent_card, mine_signals
from empire_os.a2a_data_campaign_experiments import build_data_campaign_experiments
from empire_os.a2a_data_opportunity_workflow import plan_handoffs

DEFAULT_COMMUNITY = Path("/srv/empire_os/runtime/community_intent/latest.json")
DEFAULT_GPS = Path("/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json")
OUTPUT = Path(__file__).resolve().parents[1] / "runtime" / "a2a_commercial_signal_mining"


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError("untrusted_or_oversized_snapshot")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("invalid_snapshot_root")
    return obj


def _write_local(name: str, report: dict) -> Path:
    if OUTPUT.is_symlink():
        raise ValueError("unsafe_research_directory")
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = OUTPUT / name
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("unsafe_target_path")
    data = json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".a2a_signal_", dir=str(OUTPUT), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Empire AI A2A Commercial Signal Miner (read-only)")
    p.add_argument("--community", type=Path, default=DEFAULT_COMMUNITY)
    p.add_argument("--revenue-gps", type=Path, default=DEFAULT_GPS)
    p.add_argument("--agent-card-only", action="store_true")
    p.add_argument("--write-local", action="store_true")
    args = p.parse_args(argv)
    if args.agent_card_only:
        result = agent_card()
        if args.write_local:
            _write_local("agent_card.json", result)
    else:
        result = mine_signals(
            community=_read_json(args.community),
            revenue_gps=_read_json(args.revenue_gps),
        )
        if args.write_local:
            _write_local("latest.json", result)
            experiments = build_data_campaign_experiments(result)
            _write_local("data_campaign_experiments.json", experiments)
            _write_local("a2a_handoff_plans.json", plan_handoffs(experiments))
            _write_local("campaign_briefs.json", {
                "schema_version": "empire.a2a.campaign_microsegments.v1",
                "source_report": result["schema_version"],
                "research_only": True,
                "campaigns": result["campaign_briefs"],
                "published": False,
                "outbound_sent": False,
            })
            _write_local("agent_card.json", agent_card())
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
