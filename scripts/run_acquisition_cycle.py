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
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from empire_os.acquisition_source_policy import choose_source
from empire_os.geo_registry import acquisition_markets, legacy_us_markets, market_coordinates
from empire_os.geo_scheduler import choose_market

METRO_COORDS = market_coordinates()

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
    country_scope = tuple(
        value.strip().upper()
        for value in os.getenv("EMPIRE_ACQUISITION_COUNTRIES", "").split(",")
        if value.strip()
    )
    market_set = os.getenv("EMPIRE_ACQUISITION_MARKET_SET", "").strip()
    markets = (
        legacy_us_markets()
        if market_set == "legacy_us"
        else acquisition_markets(countries=country_scope or None)
    )
    if not markets:
        raise RuntimeError("no acquisition markets configured")

    with LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = _load_state()

        choice = choose_source(
            state,
            log_path=ROOT / "runtime" / "feedback" / "crawler_runs.jsonl",
        )
        source = str(choice["source"])
        family = str(choice["family"])

        if market_set == "legacy_us":
            cursor = int(
                state.get("next_metro_index", state.get("next_index", 0))
                or 0
            ) % len(markets)
            selected = markets[cursor]
            geo = {
                "market": selected,
                "market_index": cursor,
                "next_market_index": (cursor + 1) % len(markets),
                "geo_cycle_count": int(state.get("geo_cycle_count") or 0) + 1,
                "policy": "legacy_round_robin",
                "score": selected.base_priority,
                "recent_stats": {"runs": 0.0, "accepted": 0.0, "errors": 0.0},
            }
        else:
            geo = choose_market(
                markets,
                state=state,
                source=source,
                log_path=ROOT / "runtime" / "feedback" / "crawler_runs.jsonl",
            )
        selected_market = geo["market"]
        metro_index = int(geo["market_index"])
        overpass_metro = selected_market.metro
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
            "geo_market_id": selected_market.market_id,
            "country_code": selected_market.country_code,
            "geo_country_scope": list(country_scope),
            "geo_market_set": market_set or "adaptive_global",
            "region_code": selected_market.region_code,
            "language_code": selected_market.language_code,
            "timezone": selected_market.timezone,
            "geo_policy": geo["policy"],
            "geo_score": geo["score"],
            "geo_recent_stats": geo["recent_stats"],
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
                        "geo_market_id": selected_market.market_id,
                        "country_code": selected_market.country_code,
                        "language_code": selected_market.language_code,
                        "timezone": selected_market.timezone,
                        "canonical_writes": True,
                        "real_data_only": True,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

        next_metro_index = int(geo["next_market_index"])

        STATE.write_text(
            json.dumps(
                {
                    "next_family_index": choice["next_family_index"],
                    "next_market_index": next_metro_index,
                    "next_metro_index": next_metro_index,
                    # Retain compatibility for older tooling reading next_index.
                    "next_index": next_metro_index,
                    "geo_cycle_count": int(geo["geo_cycle_count"]),
                    "next_country_index": int(
                        geo.get("next_country_index", 0)
                    ),
                    "country_market_cursors": dict(
                        geo.get("country_market_cursors") or {}
                    ),
                    "last_geo_policy": geo["policy"],
                    "last_geo_market_id": selected_market.market_id,
                    "last_country_code": selected_market.country_code,
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
