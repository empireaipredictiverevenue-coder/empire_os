#!/usr/bin/env python3
"""One bounded, OBSERVE-only research refresh on the existing buyer-scout cycle.

Uses only existing first-party evidence collectors. No email, traffic,
database or commercial authority is provided by this workflow.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from empire_os.buyer_network_research_rotation import make_research_summary

ROOT = Path("/srv/empire_os")
OUT = ROOT / "runtime/buyer_network_intelligence/research_cycle_latest.json"
STEPS = (
    "probe_buyer_network_direct_sites.py",
    "materialize_buyer_network_candidate_queue.py",
    "materialize_buyer_network_founder_shortlist.py",
    "materialize_buyer_network_founder_review_packets.py",
)


def run(
    *,
    root: Path = ROOT,
    plan_only: bool = False,
    call=None,
) -> dict:
    call = call or subprocess.run
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(root),
        "EMPIRE_MODE": "OBSERVE",
        "EMPIRE_EXECUTION_AUTHORITY": "OBSERVE",
        "OUTBOUND_ENABLED": "0",
        "EMPIRE_OUTBOUND_ENABLED": "0",
        "LIVE_OUTBOUND": "0",
    })
    steps = STEPS[:1] if plan_only else STEPS
    results = []
    for name in steps:
        args = [sys.executable, str(root / "scripts" / name)]
        if plan_only:
            args.append("--plan-only")
        try:
            completed = call(
                args, cwd=root, env=env, text=True, capture_output=True,
                timeout=120 if "probe_" in name else 55,
                check=False,
            )
            result = {
                "script": name, "exit_code": completed.returncode,
                "status": "PASS" if completed.returncode == 0 else "FAILED",
                # Avoid exposing any raw website data or credentials in logs.
                "output_tail": (completed.stdout or "")[-1250:],
                "stderr_type": "EMPTY" if not (completed.stderr or "").strip() else "PRESENT",
            }
        except subprocess.TimeoutExpired:
            result = {"script": name, "status": "TIMEOUT", "exit_code": 124}
        results.append(result)
        if result["status"] != "PASS":
            break
    if not plan_only and all(r["status"] == "PASS" for r in results):
        source = root / "runtime/buyer_network_intelligence"
        # Recompute progress after the queue/backlog have been refreshed,
        # otherwise telemetry reports outdated totals after every run.
        try:
            backlog = json.loads(
                (source / "verification_backlog_latest.json").read_text()
            )
            ledger = json.loads((source / "research_ledger_latest.json").read_text())
            direct = json.loads(
                (source / "direct_site_verification_latest.json").read_text()
            )
            previous_progress = json.loads(
                (source / "research_progress_latest.json").read_text()
            )
            refreshed = make_research_summary(
                backlog, ledger, direct.get("results") or [],
            )
            refreshed["latest_batch_domains"] = previous_progress.get(
                "latest_batch_domains", []
            )
            refreshed["latest_batch_count"] = previous_progress.get(
                "latest_batch_count", 0
            )
            path = source / "research_progress_latest.json"
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(refreshed, indent=2, sort_keys=True)+"\n")
            temp.replace(path)
        except (OSError, ValueError, TypeError, KeyError):
            # Count reporting is required to call this run successful.
            results.append({
                "script": "research_progress_reconciliation",
                "status": "FAILED", "exit_code": 1,
            })
    payload = {
        "schema_version": "empire.buyer_network_research_cycle.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAILED",
        "plan_only": plan_only,
        "steps": results,
        "outbound_sent": False,
        "db_write": False,
        "traffic_activation": False,
        "founder_review_automatic_approval": False,
        "execution_authority": "NONE",
    }
    if not plan_only:
        destination = root / "runtime/buyer_network_intelligence/research_cycle_latest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        tmp.replace(destination)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    outcome = run(plan_only=args.plan_only)
    print(json.dumps({
        "status": outcome["status"],
        "mode": outcome["mode"],
        "plan_only": outcome["plan_only"],
        "completed_steps": [r["script"] for r in outcome["steps"] if r["status"]=="PASS"],
        "failed_steps": [r["script"] for r in outcome["steps"] if r["status"]!="PASS"],
        "outbound_sent": False,
        "execution_authority": "NONE",
    }, sort_keys=True))
    return 0 if outcome["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
