"""Empire OS v3 — canonical lead-source crawler.

Runs registered REAL lead sources and materializes each LeadCandidate into
the canonical Supabase prospect inventory.

Canonical path:
    LeadCandidate
      -> prepare_candidate
      -> lookup_existing_prospect
      -> materialize_prospect
      -> ingest_prospect_atomic RPC

NO FALLBACK:
  - /v1/leads/direct is not used for canonical identity;
  - lane_leads is not written by this crawler;
  - if canonical Supabase ingest is unavailable, the candidate fails closed.

Designed for autonomous execution or one-off CLI runs.
"""

import argparse
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from empire_os.lead_sources import list_sources, _import_sources
from empire_os.prospect_ingest import (
    lookup_existing_prospect,
    materialize_prospect,
    prepare_candidate,
)

LOG_PATH = Path(
    os.environ.get(
        "CRAWLER_LOG_PATH",
        "/srv/empire_os/runtime/feedback/crawler_runs.jsonl",
    )
)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_RUN_SEC = int(os.environ.get("CRAWLER_TIMEOUT", "1800"))


def _die_on_hang(signum, frame):
    log("FATAL", f"crawler exceeded {MAX_RUN_SEC}s global timeout")
    sys.exit(124)


def log(level, msg, **fields):
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "level": level,
        "msg": msg,
        **fields,
    }
    with LOG_PATH.open("a") as fh:
        fh.write(json.dumps(event) + "\n")
    print(json.dumps(event))


def _canonical_reader(path: str, params: dict[str, str]):
    # Lazy import avoids making crawler module import depend on live bus config.
    from empire_os.autonomous_execution_bus import _rest_json
    return _rest_json("GET", path, params=params)


def _canonical_writer(payload: dict):
    # The writer calls the migration-003 ingest_prospect_atomic RPC.
    from empire_os.autonomous_execution_bus import _write_canonical_prospect
    return _write_canonical_prospect(payload)


def ingest_candidate(candidate, *, reader=None, writer=None) -> dict:
    """Run one candidate through conservative canonical acquisition."""
    reader = reader or _canonical_reader
    writer = writer or _canonical_writer

    prepared = prepare_candidate(candidate)
    lookup = lookup_existing_prospect(prepared, reader)
    return materialize_prospect(prepared, lookup, writer)


def _required_env_available(src) -> bool:
    if not src.requires:
        return True

    # Prefer already-exported environment variables.
    missing = [name for name in src.requires if not os.environ.get(name)]
    if not missing:
        return True

    # Live host/service configuration.
    env_path = Path(os.environ.get("EMPIRE_ENV_PATH", "/etc/empire_os.env"))
    try:
        content = env_path.read_text()
    except (OSError, PermissionError):
        return False

    for name in missing:
        found = False
        for line in content.splitlines():
            if line.startswith(name + "=") and line.split("=", 1)[1].strip():
                found = True
                break
        if not found:
            return False
    return True


def run_source_safe(src, metro, dry_run, max_candidates=None):
    """Run one real source with candidate-level failure isolation."""
    if src.tier != "real":
        log("SKIP", "source_not_real", source=src.name, tier=src.tier)
        return 0, 0, 0

    if not _required_env_available(src):
        log(
            "SKIP",
            "missing_required_env",
            source=src.name,
            requires=src.requires,
        )
        return 0, 0, 0

    log("INFO", "source_run_start", source=src.name)
    candidates = accepted = errors = 0

    try:
        iterator = src.run_fn(metro=metro)
        for cand in iterator:
            if max_candidates is not None and candidates >= max_candidates:
                break
            candidates += 1

            if dry_run:
                log(
                    "DRYRUN",
                    "candidate",
                    source=cand.source,
                    niche=cand.niche,
                    metro=cand.metro,
                    name=cand.name[:40],
                )
                continue

            try:
                result = ingest_candidate(cand)
            except Exception as exc:
                # Fail closed: never fall back to legacy /v1/leads/direct.
                errors += 1
                log(
                    "ERROR",
                    "canonical_ingest_failed",
                    source=cand.source,
                    name=cand.name[:40],
                    error=str(exc)[:500],
                )
                continue

            decision = str(result.get("decision") or "unknown")

            if decision == "ambiguous":
                log(
                    "SKIP",
                    "canonical_identity_ambiguous",
                    source=cand.source,
                    name=cand.name[:40],
                    reason=result.get("reason"),
                )
                continue

            accepted += 1
            prospect = result.get("prospect")
            prospect_id = (
                prospect.get("id")
                if isinstance(prospect, dict)
                else result.get("prospect_id")
            )
            log(
                "CANONICAL",
                "prospect_acquired",
                source=cand.source,
                name=cand.name[:40],
                decision=decision,
                prospect_id=prospect_id,
            )

    except Exception as exc:
        errors += 1
        log(
            "ERROR",
            "source_crashed",
            source=src.name,
            error=str(exc),
            tb=traceback.format_exc()[-200:],
        )

    log(
        "INFO",
        "source_run_done",
        source=src.name,
        candidates=candidates,
        accepted=accepted,
        errors=errors,
    )
    return candidates, accepted, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metro", default=None, help="Filter sources to one metro")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover candidates without writing canonical prospects",
    )
    parser.add_argument("--source", default=None, help="Run one source by name")
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Stop after discovering at most N candidates across the run",
    )
    args = parser.parse_args()

    if args.max_candidates is not None and args.max_candidates < 1:
        parser.error("--max-candidates must be >= 1")

    signal.signal(signal.SIGALRM, _die_on_hang)
    signal.alarm(MAX_RUN_SEC)

    log(
        "INFO",
        "crawler_run_start",
        metro=args.metro,
        dry_run=args.dry_run,
        source=args.source,
        max_candidates=args.max_candidates,
        canonical_store="supabase",
        timeout_s=MAX_RUN_SEC,
    )

    candidates_total = accepted_total = errored_total = 0
    sources_ok = sources_err = 0

    _import_sources()

    if args.source:
        from empire_os.lead_sources import _REGISTRY
        sources = [_REGISTRY[args.source]] if args.source in _REGISTRY else []
    else:
        sources = list_sources()

    remaining = args.max_candidates

    for src in sources:
        if remaining is not None and remaining <= 0:
            break

        c, accepted, errors = run_source_safe(
            src,
            args.metro,
            args.dry_run,
            max_candidates=remaining,
        )
        candidates_total += c

        if remaining is not None:
            remaining -= c
        accepted_total += accepted
        errored_total += errors
        if errors:
            sources_err += 1
        else:
            sources_ok += 1

    signal.alarm(0)

    log(
        "INFO",
        "crawler_run_done",
        candidates=candidates_total,
        accepted=accepted_total,
        errors=errored_total,
        sources_ok=sources_ok,
        sources_err=sources_err,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
