#!/usr/bin/env python3
"""Opt-in Graphify context in the EXISTING one-job Empire Coder worker.

This replaces the systemd entrypoint only after explicit rollout; it does
not start a duplicate worker or create another task queue. Graphify is
read-only and its failure never authorizes another action or blocks the
existing Coder task. Do not use without the owner-reviewed service switch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobStatus, LocalJobQueue
from empire_os.coder.worker import CoderTaskWorker
from scripts.empire_coder_worker import _apply_background_priority, parser

STATUS = "GRAPHIFY_NOT_REQUESTED"


def attach_approved_graph_context(coder: EmpireCoder, *, workspace: Path) -> str:
    if os.getenv("EMPIRE_CODER_GRAPHIFY_ENABLED", "").strip() != "1":
        return "DISABLED_BY_DEFAULT"
    try:
        from empire_os.coder.graphify_context import GraphifyContextSource
        from empire_os.coder.graphify_attach import attach_graphify_context
        from empire_os.graphify_code_snapshot import assert_snapshot_current

        root = workspace.resolve(strict=True)
        graph = root / "runtime/graphify/attested_coder_20261020/graphify-out/graph.json"
        snapshot = root / "runtime/graphify/attested_coder_manifest_20261020.json"
        for p in (graph, snapshot):
            if p.is_symlink() or not p.is_file() or p.stat().st_size > 50_000_000:
                raise ValueError("private attested Graphify snapshot unavailable")
        raw = json.loads(graph.read_text(encoding="utf-8"))
        snap = json.loads(snapshot.read_text(encoding="utf-8"))
        assert_snapshot_current(snap, source_root=root, graphify_export=raw)
        source = GraphifyContextSource(
            workspace=root, graph_path=graph, snapshot_path=snapshot,
        )
        # Runtime policy: if a source file changes while a task is processing,
        # ignore Graphify and continue existing Coder context unchanged.
        attach_graphify_context(coder, source, unavailable="skip")
        return "ATTESTED_CODE_CONTEXT_ENABLED"
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
        print(
            "GRAPHIFY_CONTEXT_DISABLED_" + type(exc).__name__,
            file=sys.stderr,
        )
        return "REJECTED_GRAPH_ONLY_BASE_CODER_INTACT"


def main(argv: list[str] | None = None) -> int:
    _apply_background_priority()
    args = parser().parse_args(argv)
    workspace = Path(args.workspace)
    coder = EmpireCoder(workspace, runtime_root=args.runtime_root)
    status = attach_approved_graph_context(coder, workspace=workspace)
    queue = LocalJobQueue(workspace, runtime_root=args.runtime_root)
    job = CoderTaskWorker(
        coder,
        queue,
        stale_seconds=args.stale_seconds,
        lease_seconds=args.lease_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        max_attempts=args.max_attempts,
    ).run_once()
    # Maintain original machine-readable stdout shape and exit codes.
    if job is None:
        print(json.dumps({
            "ok": True, "status": "idle", "execution_mode": "OBSERVE",
        }))
        print("GRAPHIFY_CONTEXT_" + status, file=sys.stderr)
        return 0
    print(json.dumps(job.as_dict(), indent=2, sort_keys=True))
    print("GRAPHIFY_CONTEXT_" + status, file=sys.stderr)
    return 0 if job.status in {
        JobStatus.COMPLETED, JobStatus.PENDING,
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
