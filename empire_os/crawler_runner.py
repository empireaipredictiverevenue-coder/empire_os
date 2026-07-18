"""Empire OS v3 — Lead Source Crawler Runner (hardened)

Runs all registered REAL lead sources, posts each LeadCandidate
to /v1/leads/direct for routing + delivery.

Designed to run as a systemd timer (every 6h) or as a one-off CLI.

Safety layer (prevents the 29h-stuck pattern):
  - signal.alarm(1800) kills the entire process at 30 min
  - each source run_fn is try/except wrapped — one broken source
    never kills the whole batch
  - explicit sys.exit(0) at end (clean oneshot exit)
  - ALL outbound http calls in lead_sources/* have timeouts 10-30s
  - systemd TimeoutStartSec=1800 as final safety net

Usage:
    /root/venv/bin/python3 -m empire_os.crawler_runner
    /root/venv/bin/python3 -m empire_os.crawler_runner --metro NYC
    /root/venv/bin/python3 -m empire_os.crawler_runner --dry-run
"""

import argparse
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

import requests

from empire_os.lead_sources import list_sources, run_all_sources, _import_sources


# ── hub URL: point at the REAL container hub (not the dead 8081 stub) ──
HUB_URL = os.environ.get(
    "EMPIRE_HUB_URL",
    "http://10.118.155.218:8000/v1/leads/direct",
)
LOG_PATH = Path("/root/feedback/crawler_runs.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# hard global timeout (seconds) — process dies if running longer
MAX_RUN_SEC = int(os.environ.get("CRAWLER_TIMEOUT", "1800"))


def _die_on_hang(signum, frame):
    msg = f"FATAL: crawler exceeded {MAX_RUN_SEC}s global timeout — killed"
    log("FATAL", msg)
    sys.exit(124)


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


def run_source_safe(src, metro, dry_run):
    """Run one source with error isolation.  Never propagates exceptions."""
    if src.tier != "real":
        log("SKIP", "source_not_real", source=src.name, tier=src.tier)
        return 0, 0, 0

    # env check (quick — just check missing vars)
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
        return 0, 0, 0

    log("INFO", "source_run_start", source=src.name)
    candidates = posted = errors = 0
    try:
        for cand in src.run_fn(metro=metro):
            candidates += 1
            if dry_run:
                log("DRYRUN", "candidate",
                    source=cand.source, niche=cand.niche,
                    metro=cand.metro, name=cand.name[:40])
                continue
            ok, resp = post_lead(cand.to_intake_payload())
            if ok:
                posted += 1
                log("POSTED", "lead",
                    source=cand.source, db_id=resp.get("db_id"),
                    lane=resp.get("lane_id"), name=cand.name[:40])
            else:
                errors += 1
                log("ERROR", "lead_post_failed",
                    source=cand.source, error=str(resp.get("error", resp)))
            time.sleep(0.5)  # polite to hub
    except Exception as e:
        errors += 1
        log("ERROR", "source_crashed",
            source=src.name, error=str(e),
            tb=traceback.format_exc()[-200:])
    log("INFO", "source_run_done",
        source=src.name, candidates=candidates,
        posted=posted, errors=errors)
    return candidates, posted, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metro", default=None,
                        help="Filter sources to one metro")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't POST to /v1/leads/direct")
    parser.add_argument("--source", default=None,
                        help="Run only one source by name")
    args = parser.parse_args()

    # ── global dead-man's switch: process dies at MAX_RUN_SEC ──
    signal.signal(signal.SIGALRM, _die_on_hang)
    signal.alarm(MAX_RUN_SEC)

    log("INFO", "crawler_run_start",
        metro=args.metro, dry_run=args.dry_run,
        source=args.source, hub_url=HUB_URL,
        timeout_s=MAX_RUN_SEC)

    candidates_total = posted_total = errored_total = 0
    sources_ok = sources_skip = sources_err = 0

    sources = list_sources() if not args.source else None
    if sources is None:
        from empire_os.lead_sources import get_source, _REGISTRY
        _import_sources()
        sources = [_REGISTRY[args.source]] if args.source in _REGISTRY else []
    else:
        from empire_os.lead_sources import _import_sources as _do_import
        _do_import()
        sources = list_sources()

    for src in sources:
        c, p, e = run_source_safe(src, args.metro, args.dry_run)
        candidates_total += c
        posted_total += p
        errored_total += e
        if e:
            sources_err += 1
        else:
            sources_ok += 1

    # disarm timeout (we finished within limit)
    signal.alarm(0)

    log("INFO", "crawler_run_done",
        candidates=candidates_total, posted=posted_total,
        errors=errored_total,
        sources_ok=sources_ok, sources_err=sources_err)
    sys.exit(0)


if __name__ == "__main__":
    main()
