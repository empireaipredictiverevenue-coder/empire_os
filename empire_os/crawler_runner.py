"""
Empire OS v3 — Lead Source Crawler Runner
==========================================

Runs all registered REAL lead sources, posts each LeadCandidate
to /v1/leads/direct for routing + delivery.

Designed to run as a systemd timer (every 6h) or as a one-off CLI.

Usage:
    /root/venv/bin/python3 -m empire_os.crawler_runner                # all metros
    /root/venv/bin/python3 -m empire_os.crawler_runner --metro NYC   # one metro
    /root/venv/bin/python3 -m empire_os.crawler_runner --dry-run     # no POSTs
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from empire_os.lead_sources import list_sources, run_all_sources, _import_sources


HUB_URL = os.environ.get("EMPIRE_HUB_URL",
                         "http://10.118.155.218:8081/v1/leads/direct")
LOG_PATH = Path("/root/feedback/crawler_runs.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def log(level, msg, **fields):
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event))


def post_lead(payload: dict) -> tuple[bool, dict]:
    try:
        r = requests.post(HUB_URL, json=payload, timeout=15)
        return r.status_code == 200, r.json() if r.status_code == 200 else {}
    except Exception as e:
        return False, {"error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metro", default=None,
                        help="Filter sources to one metro")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't POST to /v1/leads/direct")
    parser.add_argument("--source", default=None,
                        help="Run only one source by name")
    args = parser.parse_args()

    log("INFO", "crawler_run_start", metro=args.metro,
        dry_run=args.dry_run, source=args.source)

    candidates_total = 0
    posted_total = 0
    errored_total = 0

    sources = list_sources() if not args.source else None
    if sources is None:
        from empire_os.lead_sources import get_source, _REGISTRY
        _import_sources()
        sources = [_REGISTRY[args.source]] if args.source in _REGISTRY else []
    else:
        # list_sources() returns sources already registered; ensure imports ran
        from empire_os.lead_sources import _import_sources as _do_import
        _do_import()
        sources = list_sources()  # re-read after import

    for src in sources:
        if src.tier != "real":
            log("SKIP", "source_not_real",
                source=src.name, tier=src.tier)
            continue

        # Check required env vars
        env_ok = True
        for env_var in src.requires:
            env_path = Path("/root/empire_os/.env")
            if not env_path.exists():
                env_ok = False
                break
            content = env_path.read_text()
            if f"{env_var}=" not in content or content.count(f"{env_var}=\n") > 0:
                env_ok = False
                break
        if not env_ok:
            log("SKIP", "missing_required_env",
                source=src.name, requires=src.requires)
            continue

        log("INFO", "source_run_start", source=src.name)
        source_count = 0
        for cand in src.run_fn(metro=args.metro):
            source_count += 1
            candidates_total += 1

            if args.dry_run:
                log("DRYRUN", "candidate",
                    source=cand.source, niche=cand.niche,
                    metro=cand.metro, name=cand.name[:40])
                continue

            ok, resp = post_lead(cand.to_intake_payload())
            if ok:
                posted_total += 1
                log("POSTED", "lead",
                    source=cand.source, db_id=resp.get("db_id"),
                    lane=resp.get("lane_id"), name=cand.name[:40])
            else:
                errored_total += 1
                log("ERROR", "lead_post_failed",
                    source=cand.source, error=str(resp.get("error", resp)))

            time.sleep(0.5)  # be polite to hub

        log("INFO", "source_run_done",
            source=src.name, candidates=source_count)

    log("INFO", "crawler_run_done",
        candidates=candidates_total,
        posted=posted_total,
        errors=errored_total)


if __name__ == "__main__":
    main()
