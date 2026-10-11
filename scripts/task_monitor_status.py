#!/usr/bin/env python3
"""Inspect the existing, read-only completion-task monitor snapshot."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from empire_os.completion_task_monitor import OUTPUT, SCHEMA, _stamp


def inspect(root: Path, *, now: datetime | None = None) -> dict:
    clock = now or datetime.now(timezone.utc)
    path = root / OUTPUT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        generated = _stamp(data.get("generated_at"))
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "status": "UNAVAILABLE",
            "reason": "task_monitor_missing_or_invalid",
            "execution_authority": "none",
        }
    if (data.get("schema_version") != SCHEMA
            or data.get("status") != "AVAILABLE"
            or data.get("execution_authority") != "none"
            or data.get("monitoring_not_dispatch") is not True
            or generated > clock + timedelta(minutes=2)
            or clock - generated > timedelta(minutes=20)):
        return {
            "status": "STALE_OR_UNTRUSTED",
            "last_observed_at": data.get("generated_at"),
            "execution_authority": "none",
        }
    return {
        "status": "AVAILABLE",
        "generated_at": data["generated_at"],
        "checklist": data["checklist"],
        "state_counts": data["state_counts"],
        "attention_count": data["attention_count"],
        "state_changes_this_cycle": data["new_state_transition_count"],
        "recent_transitions": data["recent_transitions"][-10:],
        "top_attention": [
            {
                "line": row["line"], "task": row["task"],
                "department": row["department"], "state": row["state"],
                "reason": row["attention_reason"],
                "next_evidence_step": row["next_evidence_step"],
            } for row in data["top_attention"][:10]
        ],
        "monitoring_not_dispatch": True,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    summary = inspect(Path(args.repo_root))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "AVAILABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
