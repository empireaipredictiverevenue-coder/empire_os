#!/usr/bin/env python3
"""Bounded real-source acquisition cycle.

Rotates one metro per run, runs only the real Overpass source, and relies on
crawler_runner's quality/idempotency/canonical-ingest boundaries.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from empire_os.lead_sources.overpass import METRO_COORDS

ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime" / "acquisition"
STATE = RUNTIME / "state.json"
LATEST = RUNTIME / "latest.json"
LAST_SUCCESS = RUNTIME / "last_success.json"
LOCK = RUNTIME / "cycle.lock"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_index(count: int) -> int:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return int(data.get("next_index", 0)) % count
    except Exception:
        return 0


def run_cycle(*, max_candidates: int = 10) -> dict:
    if max_candidates < 1 or max_candidates > 25:
        raise ValueError("max_candidates must be between 1 and 25")

    RUNTIME.mkdir(parents=True, exist_ok=True)
    metros = list(METRO_COORDS)
    if not metros:
        raise RuntimeError("no acquisition metros configured")

    with LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        index = _load_index(len(metros))
        metro = metros[index]

        command = [
            sys.executable,
            "-m",
            "empire_os.crawler_runner",
            "--source",
            "overpass",
            "--metro",
            metro,
            "--max-candidates",
            str(max_candidates),
        ]
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

        result = {
            "schema_version": "acquisition_cycle.v1",
            "started_at": _now(),
            "metro": metro,
            "max_candidates": max_candidates,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": (completed.stdout or "")[-8000:],
            "stderr_tail": (completed.stderr or "")[-4000:],
            "source": "overpass",
            "real_data_only": True,
            "outreach_enabled": False,
            "payment_enabled": False,
        }

        LATEST.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if (
            result["ok"]
            and '"msg": "prospect_acquired"' in (completed.stdout or "")
        ):
            LAST_SUCCESS.write_text(
                json.dumps(
                    {
                        "schema_version": "acquisition_success.v1",
                        "observed_at": _now(),
                        "source": "overpass",
                        "metro": metro,
                        "canonical_writes": True,
                        "real_data_only": True,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

        # Always rotate after a bounded attempt. A dense/temporarily overloaded
        # metro must not pin acquisition indefinitely. Failure remains visible
        # in latest.json while the next scheduled run tries another real metro.
        STATE.write_text(
            json.dumps(
                {
                    "next_index": (index + 1) % len(metros),
                    "last_metro": metro,
                    "last_ok": result["ok"],
                    "updated_at": _now(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-candidates", type=int, default=10)
    args = parser.parse_args()
    result = run_cycle(max_candidates=args.max_candidates)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
