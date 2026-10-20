"""Fail-closed, read-only deployment signoff for the EXISTING Graphify Coder adapter.

Two independent judgements:
* CODE_ADAPTER: installed, healthy, attested and reversibly deployed.
* CODER_IMPLEMENTATION: genuine execution still needs owner approval,
  clean authorized workspace and original implementation outcomes.

This does not start workers, change systemd, write reports or auto-promote jobs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from empire_os.coder.graphify_change_review import GraphifyChangeReviewer
from empire_os.coder.graphify_context import GraphifyContextSource
from empire_os.coder.repo import RepoIntelligence
from empire_os.graphify_implementation_funnel import review_implementation_funnel
from scripts.review_graphify_graph_health_20261020 import review as graph_health

SCHEMA = "empire.graphify.production_release_gate.v1"
GRAPH = "runtime/graphify/attested_coder_20261020/graphify-out/graph.json"
MANIFEST = "runtime/graphify/attested_coder_manifest_20261020.json"
RELEASE = "runtime/graphify/curated_expansion_release_impact_20261020.json"
BACKUP = "runtime/graphify/curated_expansion_backup_impact_20261020"
# Explicit additive receipt: do not overwrite historical private evidence.
NEXT_RELEASE = "runtime/graphify/curated_expansion_release_implguard_20261020.json"
NEXT_BACKUP = "runtime/graphify/curated_expansion_backup_implguard_20261020"
REQUIRED_FLAGS = (
    "EMPIRE_CODER_GRAPHIFY_ENABLED=1",
    "EMPIRE_CODER_GRAPHIFY_PREPATCH_OBSERVE=1",
)
EXACT_WORKER = "scripts/run_graphify_coder_worker_20261020.py"
REQUIRED_CODE = (
    "empire_os/coder/graphify_context.py",
    "empire_os/coder/graphify_attach.py",
    "empire_os/coder/graphify_change_review.py",
    "empire_os/coder/graphify_prepatch.py",
    "scripts/run_graphify_coder_worker_20261020.py",
    "scripts/review_graphify_graph_health_20261020.py",
    "scripts/review_graphify_implementation_funnel_20261020.py",
)


def _read_receipt(path: Path) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= 500_000
            or path.stat().st_mode & 0o077):
        raise ValueError("private release receipt unavailable or not private")
    packet = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise ValueError("invalid private release receipt")
    return packet


def verify_release_custody(root: Path) -> dict[str, Any]:
    """Check BOTH immutable Graphify release generations and rollback hashes.

    The initial public code-adapter release is unchanged. A subsequent
    indexed-source refresh is valid only when its private backup exactly
    matches the preceding release's current file digests.
    """
    root = Path(root)
    try:
        prior = _read_receipt(root / RELEASE)
        if prior.get("status") != "LIVE_CURATED_REAL_SOURCE_EXPANSION_VERIFIED":
            raise ValueError("unexpected original release status")
        for filename in (GRAPH, MANIFEST):
            path = root / filename
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 50_000_000:
                raise ValueError("invalid currently published private evidence")
        current = {
            "graph": sha256((root / GRAPH).read_bytes()).hexdigest(),
            "manifest": sha256((root / MANIFEST).read_bytes()).hexdigest(),
        }

        def verify_private_backup(backup_relative: str, packet: Mapping[str, Any]) -> None:
            backup = root / backup_relative
            if backup.is_symlink() or not backup.is_dir():
                raise ValueError("private rollback backup absent")
            for filename, expected in (
                ("graph.json", "prior_graph_file_sha256"),
                ("manifest.json", "prior_snapshot_file_sha256"),
            ):
                path = backup / filename
                if (path.is_symlink() or not path.is_file()
                        or path.stat().st_mode & 0o077
                        or sha256(path.read_bytes()).hexdigest() != packet.get(expected)):
                    raise ValueError("private rollback digest mismatch")

        verify_private_backup(BACKUP, prior)
        latest = prior
        release_generation = "ORIGINAL_ATTESTED_CODE"
        follow_up = root / NEXT_RELEASE
        if follow_up.exists() or follow_up.is_symlink():
            newer = _read_receipt(follow_up)
            if newer.get("status") != "LIVE_CURATED_REAL_SOURCE_EXPANSION_VERIFIED":
                raise ValueError("invalid next code-only release")
            if (newer.get("prior_graph_file_sha256") != prior.get("current_graph_sha256")
                    or newer.get("prior_snapshot_file_sha256") != prior.get("current_manifest_sha256")):
                raise ValueError("Graphify release provenance chain broken")
            verify_private_backup(NEXT_BACKUP, newer)
            latest = newer
            release_generation = "IMPLEMENT_ADMISSION_REFRESH"
        if (current["graph"] != latest.get("current_graph_sha256")
                or current["manifest"] != latest.get("current_manifest_sha256")):
            raise ValueError("current Graphify release drifted")
        return {
            "status": "PRIVATE_ROLLBACK_AND_RELEASE_ATTESTED",
            "rollback_available": True,
            "release_generation": release_generation,
            "reason_code": None,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {
            "status": "DEPLOYMENT_HOLD",
            "rollback_available": False,
            "release_generation": "UNVERIFIED",
            "reason_code": "PRIVATE_RELEASE_CUSTODY_UNVERIFIED",
        }


def _show(unit: str, *properties: str) -> dict[str, str]:
    result = subprocess.run(
        ["systemctl", "show", unit, *[arg for name in properties for arg in ("-p", name)]],
        capture_output=True, text=True, timeout=12, check=False,
    )
    if result.returncode != 0:
        raise ValueError("service configuration unavailable")
    return dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )


def inspect_existing_service() -> dict[str, Any]:
    """Status only: inactive/dead is normal for a successful oneshot worker."""
    try:
        service = _show(
            "empire-coder-worker.service", "ActiveState", "SubState",
            "Result", "ExecStart", "Environment",
        )
        timer = _show(
            "empire-coder-worker.timer", "ActiveState", "SubState",
        )
        argv = service.get("ExecStart", "")
        flags = service.get("Environment", "")
        worker_ok = EXACT_WORKER in argv
        flags_ok = all(value in flags.split() for value in REQUIRED_FLAGS)
        timer_ok = timer.get("ActiveState") == "active"
        service_ok = service.get("Result") == "success" and (
            service.get("ActiveState") in ("active", "activating", "inactive")
        )
        return {
            "status": "ACTIVE_OR_SUCCESSFUL_ONESHOT"
            if all((worker_ok, flags_ok, timer_ok, service_ok))
            else "SERVICE_CONFIGURATION_HOLD",
            "existing_worker_entrypoint_verified": worker_ok,
            "context_and_prepatch_flags_present": flags_ok,
            "original_timer_active": timer_ok,
            "service_result_success": service_ok,
            "new_worker_created": False,
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {
            "status": "SERVICE_READBACK_UNAVAILABLE",
            "existing_worker_entrypoint_verified": False,
            "context_and_prepatch_flags_present": False,
            "original_timer_active": False,
            "service_result_success": False,
            "new_worker_created": False,
        }


def source_owned_modules_clean(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", *REQUIRED_CODE],
        capture_output=True, text=True, check=False, timeout=20,
    )
    return result.returncode == 0 and not result.stdout.strip()


def perform_code_smoke(root: Path) -> dict[str, Any]:
    """Real AST symbol and direct dependency checks, with no Coder writes."""
    source = GraphifyContextSource(
        workspace=root,
        graph_path=root / GRAPH,
        snapshot_path=root / MANIFEST,
    )
    actual = source.documents(
        terms=("ContextBuilder",), repo=RepoIntelligence(root),
        max_docs=3, max_chars=2200,
    )
    retrieved = any(
        doc.path == "empire_os/coder/context.py" for doc in actual
    )
    impact = GraphifyChangeReviewer(
        workspace=root,
        graph_path=root / GRAPH,
        snapshot_path=root / MANIFEST,
    ).review(("empire_os/coder/models.py",), max_affected=10)
    return {
        "status": "REAL_SOURCE_CONTEXT_AND_IMPACT_VERIFIED"
        if retrieved and impact.get("source_graph_attested") is True
        and impact.get("affected_source_count", 0) > 0
        and impact.get("patch_authorized") is False
        else "CODE_SMOKE_HOLD",
        "real_context_source_found": retrieved,
        "direct_dependency_candidates": impact.get("affected_source_count", 0),
        "automatic_patch_authorized": False,
    }


def classify_release(
    *, graph: Mapping[str, Any], custody: Mapping[str, Any],
    service: Mapping[str, Any], smoke: Mapping[str, Any],
    owned_clean: bool, funnel: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure classification: deployment readiness != authority to implement."""
    graph_ok = (
        graph.get("status") == "CURRENT_ATTESTED_CODE"
        and graph.get("indexed_source_count", 0) >= 20
        and graph.get("indexed_source_count") == graph.get("unchanged_source_count")
        and all(x.get("exact_symbol_found") for x in graph.get("real_code_symbol_coverage", []))
        and len(graph.get("real_code_symbol_coverage", [])) >= 4
    )
    custody_ok = custody.get("rollback_available") is True
    service_ok = service.get("status") == "ACTIVE_OR_SUCCESSFUL_ONESHOT"
    smoke_ok = smoke.get("status") == "REAL_SOURCE_CONTEXT_AND_IMPACT_VERIFIED"
    held = [
        reason for reason, condition in (
            ("SOURCE_GRAPH_NOT_ATTESTED", not graph_ok),
            ("RELEASE_OR_ROLLBACK_UNVERIFIED", not custody_ok),
            ("CODER_SERVICE_OR_TIMER_UNREADY", not service_ok),
            ("REAL_CODE_SMOKE_FAILED", not smoke_ok),
            ("GRAPHIFY_OWNED_SOURCE_UNCOMMITTED", not owned_clean),
        ) if condition
    ]
    pipeline_holds = funnel.get("blockers")
    if not isinstance(pipeline_holds, list) or not all(isinstance(x, str) for x in pipeline_holds):
        pipeline_holds = ["CANONICAL_CODER_FUNNEL_UNVERIFIED"]
    ready = not held
    return {
        "graphify_release_status": (
            "DEPLOYED_CODE_ADAPTER_VERIFIED" if ready
            else "GRAPHIFY_RELEASE_HOLD"
        ),
        "coder_implementation_status": (
            "HELD_BY_EXISTING_OWNERS" if pipeline_holds
            else "NO_KNOWN_FUNNEL_BLOCKERS_OUTCOME_STILL_UNPROVEN"
        ),
        "graphify_release_blockers": held,
        "existing_coder_owner_blockers": pipeline_holds,
        "code_adapter_deployed_and_usable": ready,
        "end_to_end_verified_implementation": False,
        "commercial_activation_authorized": False,
    }


def review_deployment_readiness(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    graph = graph_health(root)
    custody = verify_release_custody(root)
    service = inspect_existing_service()
    try:
        smoke = (
            perform_code_smoke(root)
            if graph.get("status") == "CURRENT_ATTESTED_CODE" else
            {"status": "CODE_SMOKE_HOLD", "real_context_source_found": False,
             "direct_dependency_candidates": 0, "automatic_patch_authorized": False}
        )
    except (OSError, ValueError, TypeError, KeyError):
        smoke = {"status": "CODE_SMOKE_HOLD", "real_context_source_found": False,
                 "direct_dependency_candidates": 0, "automatic_patch_authorized": False}
    owned_clean = source_owned_modules_clean(root)
    try:
        funnel = review_implementation_funnel(
            root, as_of=datetime.now(timezone.utc), lookback_hours=24,
        )
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        funnel = {"blockers": ["CANONICAL_CODER_FUNNEL_UNVERIFIED"]}
    decision = classify_release(
        graph=graph, custody=custody, service=service,
        smoke=smoke, owned_clean=owned_clean, funnel=funnel,
    )
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_DEPLOYMENT_REVIEW",
        "execution_authority": "none",
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        **decision,
        "live_code_graph": {
            "status": graph.get("status"),
            "indexed_real_source_files": graph.get("indexed_source_count"),
            "source_files_unchanged": graph.get("unchanged_source_count"),
            "code_nodes": graph.get("code_graph_nodes"),
            "code_edges": graph.get("code_graph_edges"),
        },
        "rollback": custody,
        "existing_coder_service": service,
        "real_code_smoke": smoke,
        "graphify_owned_source_clean": owned_clean,
        "synthetic_business_data_created": False,
        "new_tasks_or_workers_created": False,
        "existing_service_restarted": False,
        "source_files_modified": False,
    }
