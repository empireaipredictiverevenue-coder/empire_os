#!/usr/bin/env python3
"""Run the bounded Predictive Cloud opportunity discovery loop once.

Sequence:
1. Opportunity Radar
2. bounded public Opportunity Research
3. truth-preserving Opportunity Factory intake

No outbound, terms, payments, revenue recognition or authority expansion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

from empire_os.opportunity_factory_intake import refresh_factory_intake
from empire_os.opportunity_radar import refresh_opportunity_radar
from empire_os.opportunity_research import refresh_opportunity_research


OUTPUT = Path("runtime/opportunity_radar/loop_latest.json")


def run_opportunity_loop(
    repo_root: Path,
    *,
    radar_fn: Callable[[Path], dict[str, Any]] = refresh_opportunity_radar,
    research_fn: Callable[[Path], dict[str, Any]] = refresh_opportunity_research,
    intake_fn: Callable[[Path], dict[str, Any]] = refresh_factory_intake,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    steps: list[dict[str, Any]] = []

    for name, fn in (
        ("opportunity_radar", radar_fn),
        ("opportunity_research", research_fn),
        ("opportunity_factory_intake", intake_fn),
    ):
        try:
            result = fn(repo_root)
            steps.append({
                "step": name,
                "ok": True,
                "summary": {
                    key: result.get(key)
                    for key in (
                        "candidate_count",
                        "factory_ready_count",
                        "blocked_count",
                        "researched_candidate_count",
                        "observation_count",
                        "error_count",
                    )
                    if key in result
                },
            })
        except Exception as exc:
            steps.append({
                "step": name,
                "ok": False,
                "error": str(exc)[:1000],
            })
            # Later steps depend on earlier snapshots. Fail closed rather than
            # treating stale data as a successful current cycle.
            break

    finished = datetime.now(timezone.utc)
    payload = {
        "schema_version": "empire.predictive_cloud.opportunity_loop.v1",
        "mode": "OBSERVE",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "ok": len(steps) == 3 and all(row["ok"] for row in steps),
        "steps": steps,
        "automatic_internal_research": True,
        "automatic_external_execution_allowed": False,
        "outreach_sent": False,
        "commercial_terms_accepted": False,
        "payment_action": False,
        "revenue_recognized": False,
        "execution_authority": "none",
    }

    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = run_opportunity_loop(Path(args.repo_root).resolve())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
