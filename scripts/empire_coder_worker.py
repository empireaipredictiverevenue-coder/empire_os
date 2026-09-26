#!/usr/bin/env python3
"""Run one resumable Empire Coder plan/proposal job."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobStatus, LocalJobQueue
from empire_os.coder.worker import CoderTaskWorker


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Empire Coder resumable proposal worker"
    )
    p.add_argument(
        "--workspace",
        default=os.getenv(
            "EMPIRE_CODER_WORKSPACE",
            "/srv/empire_os",
        ),
    )
    p.add_argument(
        "--runtime-root",
        default=os.getenv(
            "EMPIRE_CODER_RUNTIME_ROOT",
            "/srv/empire_os/runtime/coder",
        ),
    )
    p.add_argument(
        "--stale-seconds",
        type=int,
        default=_env_int(
            "EMPIRE_CODER_JOB_STALE_SECONDS",
            240,
        ),
    )
    p.add_argument(
        "--lease-seconds",
        type=int,
        default=_env_int(
            "EMPIRE_CODER_JOB_LEASE_SECONDS",
            240,
        ),
    )
    p.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=_env_int(
            "EMPIRE_CODER_JOB_HEARTBEAT_SECONDS",
            30,
        ),
    )
    p.add_argument(
        "--max-attempts",
        type=int,
        default=_env_int(
            "EMPIRE_CODER_JOB_MAX_ATTEMPTS",
            3,
        ),
    )
    p.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="process at most one queued job",
    )
    return p


def _apply_background_priority(target_nice: int = 10) -> None:
    try:
        current = os.nice(0)
        if current < target_nice:
            os.nice(target_nice - current)
    except OSError:
        pass


def main(argv=None) -> int:
    _apply_background_priority()
    args = parser().parse_args(argv)
    coder = EmpireCoder(
        Path(args.workspace),
        runtime_root=args.runtime_root,
    )
    queue = LocalJobQueue(
        Path(args.workspace),
        runtime_root=args.runtime_root,
    )
    job = CoderTaskWorker(
        coder,
        queue,
        stale_seconds=args.stale_seconds,
        lease_seconds=args.lease_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        max_attempts=args.max_attempts,
    ).run_once()

    if job is None:
        print(json.dumps({
            "ok": True,
            "status": "idle",
            "execution_mode": "OBSERVE",
        }))
        return 0

    print(json.dumps(
        job.as_dict(),
        indent=2,
        sort_keys=True,
    ))
    return 0 if job.status in {
        JobStatus.COMPLETED,
        JobStatus.PENDING,
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
