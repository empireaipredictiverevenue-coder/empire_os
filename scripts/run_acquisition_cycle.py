#!/usr/bin/env python3
"""Bounded multi-source real acquisition cycle.

Rotates broad local-business discovery with specialist signal sources while
keeping every accepted candidate on the same canonical Supabase ingest path.

No source writes legacy lead tables. No source sends outreach or moves funds.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from empire_os.acquisition_source_policy import choose_source
from empire_os.lead_sources.overpass import METRO_COORDS

ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime" / "acquisition"
STATE = RUNTIME / "state.json"
LATEST = RUNTIME / "latest.json"
LAST_SUCCESS = RUNTIME / "last_success.json"
LOCK = RUNTIME / "cycle.lock"

# Diversified acquisition portfolio. No single discovery engine may dominate
# the commercial pipeline. Broad business discovery gets three slots; the
# remaining slots are independent intent/event/public-record sources.
SOURCE_ROTATION = (
    "overpass",
    "biz_search",
    "reddit",
    "nws_alerts",
    "overpass",
    "permits",
    "chicago_311",
    "nyc_hpd",
    "courtlistener",
    "overpass",
)

# These sources own their own geography/query rotation and should not inherit
# an arbitrary Overpass metro.
SOURCE_METRO = {
    "reddit": None,
    "permits": "NYC",
    "chicago_311": "CHI",
    "courtlistener": None,
    "nyc_hpd": "NYC",
    "nws_alerts": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict:
    try:
        value = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def run_cycle(*, max_candidates: int = 10) -> dict:
    if max_candidates < 1 or max_candidates > 25:
        raise ValueError("max_candidates must be between 1 and 25")

    RUNTIME.mkdir(parents=True, exist_ok=True)
    metros = list(METRO_COORDS)
    if not metros:
        raise RuntimeError("no acquisition metros configured")

    with LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = _load_state()

        choice = choose_source(
            state,
            log_path=ROOT / "runtime" / "feedback" / "crawler_runs.jsonl",
        )
        source = str(choice["source"])
        family = str(choice["family"])

        metro_index = int(
            state.get("next_metro_index", state.get("next_index", 0))
        ) % len(metros)
        overpass_metro = metros[metro_index]
        metro = (
            overpass_metro
            if source in {"overpass", "biz_search"}
            else SOURCE_METRO.get(source)
        )

        command = [
            sys.executable,
            "-m",
            "empire_os.crawler_runner",
            "--source",
            source,
            "--max-candidates",
            str(max_candidates),
        ]
        if metro:
            command.extend(["--metro", metro])

        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        prospect_acquired = '"msg": "prospect_acquired"' in stdout
        signal_queued = '"msg": "signal_queued"' in stdout
        acquired = prospect_acquired or signal_queued

        result = {
            "schema_version": "acquisition_cycle.v2",
            "started_at": _now(),
            "source": source,
            "source_family": family,
            "source_policy": choice.get("policy"),
            "source_recent_stats": choice.get("recent_stats") or {},
            "metro": metro,
            "overpass_metro_cursor": overpass_metro,
            "max_candidates": max_candidates,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "canonical_acquisition_observed": acquired,
            "prospect_acquired": prospect_acquired,
            "signal_queued": signal_queued,
            "stdout_tail": stdout[-8000:],
            "stderr_tail": stderr[-4000:],
            "real_data_only": True,
            "canonical_store": "supabase",
            "outreach_enabled": False,
            "payment_enabled": False,
        }

        LATEST.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if result["ok"] and acquired:
            LAST_SUCCESS.write_text(
                json.dumps(
                    {
                        "schema_version": "acquisition_success.v2",
                        "observed_at": _now(),
                        "source": source,
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

        next_metro_index = metro_index
        if source in {"overpass", "biz_search"}:
            next_metro_index = (metro_index + 1) % len(metros)

        STATE.write_text(
            json.dumps(
                {
                    "next_family_index": choice["next_family_index"],
                    "next_metro_index": next_metro_index,
                    # Retain compatibility for older tooling reading next_index.
                    "next_index": next_metro_index,
                    "last_source": source,
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
