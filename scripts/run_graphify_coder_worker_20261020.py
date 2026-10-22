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
import stat
from pathlib import Path
import sys

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
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


def attach_approved_prepatch_observer(coder: EmpireCoder) -> str:
    """Optional read-only hook, only after Graphify source attestation."""
    if os.getenv("EMPIRE_CODER_GRAPHIFY_PREPATCH_OBSERVE", "").strip() != "1":
        return "DISABLED_BY_DEFAULT"
    try:
        from empire_os.coder.graphify_prepatch import attach_graphify_prepatch_observer
        attach_graphify_prepatch_observer(coder)
    except (ValueError, TypeError) as exc:
        print("GRAPHIFY_PREPATCH_DISABLED_" + type(exc).__name__, file=sys.stderr)
        return "NO_ATTESTED_GRAPH_BASE_CODER_UNCHANGED"
    return "READ_ONLY_PREPATCH_OBSERVER_ENABLED"


def _print_prepatch_usage(coder: EmpireCoder, job=None) -> None:
    if job is None:
        return
    observer = getattr(coder, "_graphify_prepatch_observer", None)
    if observer is None:
        return
    counts = observer.metrics_snapshot()
    # Aggregate numbers and job category only; no task identifiers, source
    # paths, patch contents, prompts or customer/private record fields.
    counts["job_kind"] = job.kind.value
    counts["job_status"] = job.status.value
    # Read the original result of THIS SAME existing job, not a guessed
    # temporal join across unrelated log lines. Never emit patch details.
    source_result = getattr(job, "result", None)
    result = source_result if isinstance(source_result, dict) else {}
    completed_implementation = (
        job.kind is JobKind.IMPLEMENT and job.status is JobStatus.COMPLETED
    )
    counts["coder_reported_patch_applied"] = (
        result.get("applied") if completed_implementation
        and type(result.get("applied")) is bool else None
    )
    verification = result.get("verification")
    if not completed_implementation or not isinstance(verification, dict):
        verification = {}
    verdict = verification.get("verdict")
    counts["coder_verification_verdict"] = (
        verdict if verdict in ("PASS", "PASS_WITH_WARNINGS", "FAIL")
        else "UNKNOWN"
    )
    # Source verdict = existing Coder, not external runtime verification.
    counts["same_job_result_observed"] = completed_implementation
    print("GRAPHIFY_PREPATCH_USAGE " + json.dumps(counts, sort_keys=True),
          file=sys.stderr)


def _print_context_usage(coder: EmpireCoder, job=None) -> None:
    """Emit count-only telemetry on stderr, never prompt or source metadata."""
    context = getattr(coder, "context", None)
    report = getattr(context, "metrics_snapshot", None)
    if callable(report) and job is not None:
        counts = report()
        # Generic enum values only; NEVER emit job IDs, task text,
        # customer data, file paths, private terms or URLs.
        counts["job_kind"] = job.kind.value
        counts["job_status"] = job.status.value
        print(
            "GRAPHIFY_CONTEXT_USAGE " + json.dumps(counts, sort_keys=True),
            file=sys.stderr,
        )


def _consume_once_identity_probe_marker(
    marker: Path = Path(
        "/srv/empire_os/runtime/coder/agent_signing_observe_once_20261022.flag"
    ),
) -> bool:
    """Consume only our exact small, owner-private observe-only marker.

    It cannot enable messaging, open a task, or register a key; the marker
    only opts in to one transient process signing observation.
    """
    expected = b"EMPIRE_CODER_PROCESS_SIGNING_OBSERVE_ONLY_V1" + bytes((10,))
    try:
        fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size != len(expected)
            or os.read(fd, len(expected) + 1) != expected
        ):
            return False
        current = marker.stat(follow_symlinks=False)
        if current.st_ino != info.st_ino or current.st_dev != info.st_dev:
            return False
        marker.unlink()
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def _observe_existing_worker_signing_identity() -> None:
    """Optional proof in THIS existing worker's main process only.

    Explicitly disabled unless the service owner enables a read-only
    observation flag. No persistent key, task, peer message, or new worker.
    An attested self-issued signature never enrols a trusted agent.
    """
    if (
        os.getenv("EMPIRE_CODER_AGENT_SIGNING_OBSERVE", "").strip() != "1"
        and not _consume_once_identity_probe_marker()
    ):
        return
    try:
        from empire_os.managed_agent_signing_probe import (
            inspect_actual_coder_signing_process,
        )
        receipt = inspect_actual_coder_signing_process()
        # Public key and signed payload only. Never persist private material,
        # credentials, task contents or model responses.
        print(
            "CODER_AGENT_SIGNATURE_OBSERVE "
            + json.dumps(receipt, sort_keys=True),
            file=sys.stderr,
        )
    except Exception as exc:
        # Telemetry cannot stop or alter the pre-existing Coder job.
        print(
            "CODER_AGENT_SIGNATURE_OBSERVE_HELD_" + type(exc).__name__,
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    _apply_background_priority()
    _observe_existing_worker_signing_identity()
    args = parser().parse_args(argv)
    workspace = Path(args.workspace)
    coder = EmpireCoder(workspace, runtime_root=args.runtime_root)
    status = attach_approved_graph_context(coder, workspace=workspace)
    prepatch_status = attach_approved_prepatch_observer(coder)
    queue = LocalJobQueue(workspace, runtime_root=args.runtime_root)
    job = CoderTaskWorker(
        coder,
        queue,
        stale_seconds=args.stale_seconds,
        lease_seconds=args.lease_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        max_attempts=args.max_attempts,
    ).run_once()
    _print_context_usage(coder, job)
    _print_prepatch_usage(coder, job)
    if job is not None:
        print("GRAPHIFY_PREPATCH_" + prepatch_status, file=sys.stderr)
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
