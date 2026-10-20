"""Read-only Graphify diagnosis of the EXISTING Coder implementation funnel.

Authoritative sources: Coder LocalJobQueue's original per-job state,
Founder's original directive records, canonical supervisor dirty-worktree
policy, and the Coder plan-promotion contract validator.

No dispatch, task creation, authority transfer or synthetic evidence.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from empire_os.coder.plan_promotion import _validate_contract
from empire_os.graphify_writer_provider_probe import probe_current_writer_provider

SCHEMA = "empire.graphify.implementation_funnel_readiness.v1"
MAX_BYTES = 262_144
MAX_JOBS = 100_000
MAX_DIRECTIVES = 10_000
STATES = ("pending", "running", "delegated", "completed", "failed")


def _original_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        if not 0 < path.stat().st_size <= MAX_BYTES:
            return None
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    return body if isinstance(body, dict) else None


def _within(value: Any, *, earliest: datetime, latest: datetime) -> bool:
    if not isinstance(value, str):
        return False
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return instant.tzinfo is not None and earliest <= instant.astimezone(timezone.utc) <= latest


def _git_dirty(root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, check=False, timeout=40,
    )
    if completed.returncode != 0:
        raise ValueError("canonical production Git status unavailable")
    changed = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        rel = line[3:].split(" -> ")[-1].strip()
        # Reuse the existing owner policy: only recovery/ and toop/ are
        # exempt; Graphify may not loosen this policy itself.
        if rel.split("/", 1)[0] in ("recovery", "toop"):
            continue
        changed.append(rel)
    return {
        "nonprotected_dirty_file_count": len(changed),
        "supervisor_dirty_checkout_gate": bool(changed),
        "dirty_paths_exported": False,
    }


def review_implementation_funnel(
    repo_root: str | Path, *, as_of: datetime,
    lookback_hours: int = 24,
) -> dict[str, Any]:
    """Separate PLAN promotion and founder-directive implementation holds."""
    if as_of.tzinfo is None:
        raise ValueError("timezone-aware as_of required")
    if type(lookback_hours) is not int or not 1 <= lookback_hours <= 90 * 24:
        raise ValueError("invalid lookback")
    root = Path(repo_root).resolve(strict=True)
    jobs = root / "runtime/coder/jobs"
    if jobs.is_symlink() or not jobs.is_dir():
        raise ValueError("original Coder queue directory required")
    current = as_of.astimezone(timezone.utc)
    earliest = current - timedelta(hours=lookback_hours)
    plan = Counter()
    recent = Counter()
    scanned = 0
    for state in STATES:
        folder = jobs / state
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("invalid original queue state directory")
        for file in folder.glob("*.json"):
            scanned += 1
            if scanned > MAX_JOBS:
                raise ValueError("job inventory exceeds limit")
            row = _original_json(file)
            if row is None or row.get("id") != file.stem or row.get("kind") not in (
                "PLAN", "IMPLEMENT", "VERIFY", "NEXT_COMMAND"
            ):
                continue
            if row.get("status") != state.upper():
                continue
            if _within(row.get("updated_at"), earliest=earliest, latest=current):
                recent[f"{row['kind']}/{state}"] += 1
            if state != "completed" or row.get("kind") != "PLAN":
                continue
            result = row.get("result")
            if not isinstance(result, Mapping) or result.get("proposal_persisted") is not True:
                continue
            plan["completed_persisted_plans"] += 1
            is_recent = _within(
                row.get("updated_at"), earliest=earliest, latest=current
            )
            if is_recent:
                plan["recent_completed_persisted_plans"] += 1
            payload = row.get("payload")
            contract = payload.get("promotion_contract") if isinstance(payload, Mapping) else None
            if not isinstance(contract, Mapping):
                plan["without_promotion_contract"] += 1
                if is_recent:
                    plan["recent_without_promotion_contract"] += 1
                continue
            kind, blockers = _validate_contract(contract)
            category = (
                "STRUCTURALLY_VALID_VERIFY" if kind and kind.value == "VERIFY" and not blockers
                else "STRUCTURALLY_VALID_IMPLEMENT" if kind and kind.value == "IMPLEMENT" and not blockers
                else "INVALID_CONTRACT"
            )
            plan[category] += 1
            if is_recent:
                plan["recent_" + category] += 1
            if blockers:
                plan["contract_blocker_fields_total"] += len(blockers)

    directives_root = root / "runtime/founder_directives/records"
    if directives_root.is_symlink() or not directives_root.is_dir():
        raise ValueError("original founder directive records missing")
    directives = Counter()
    failure_classes = Counter()
    entries = 0
    for file in directives_root.glob("*.json"):
        entries += 1
        if entries > MAX_DIRECTIVES:
            raise ValueError("founder directive inventory exceeds limit")
        row = _original_json(file)
        if row is None or row.get("id") != file.stem:
            continue
        stage = row.get("status")
        if isinstance(stage, str) and len(stage) <= 64:
            directives[stage] += 1
        if stage == "implementation_ready":
            authority = row.get("authority")
            directives["ready_authority_internal_plan" if authority == "internal_plan"
                       else "ready_other_authority"] += 1
        if stage == "implementation_failed":
            original = row.get("implementation_result")
            original = original if isinstance(original, Mapping) else {}
            original_commit = original.get("commit")
            original_commit = original_commit if isinstance(original_commit, Mapping) else {}
            reason = original_commit.get("reason")
            known_commit_reasons = {
                "candidate_not_applied", "verification_not_passed",
                "git_diff_check_failed", "no_candidate_diff",
                "git_status_failed", "git_add_failed",
            }
            if reason in known_commit_reasons:
                failure_classes["commit_" + reason] += 1
            else:
                error = original.get("error")
                message = error.lower() if isinstance(error, str) else ""
                if any(x in message for x in ("model", "provider", "inference")):
                    failure_classes["model_or_provider"] += 1
                elif "lease" in message:
                    failure_classes["execution_lease"] += 1
                elif any(x in message for x in ("policy", "permission")):
                    failure_classes["policy_or_permission"] += 1
                else:
                    failure_classes["other_or_unknown"] += 1

    checkout = _git_dirty(root)
    plan_has_implement_contract = plan["STRUCTURALLY_VALID_IMPLEMENT"] > 0
    next_actions = [
        {
            "owner": "existing_coder_plan_promotion_owner",
            "action": "VERIFY_AND_SUPPLY_EXPLICIT_PROMOTION_CONTRACT_FOR_AUTHORISED_WORK_ONLY",
            "requires": [
                "authenticated_existing_owner_request",
                "authenticated_execution_plane_authority",
                "internal_write_authority",
                "explicit_allowed_paths",
                "current_execution_plane_request_id",
                "nonconflicting_lease_resources",
                "real_required_tests",
            ],
            "automatic_enqueuing_authorized": False,
        },
        {
            "owner": "existing_founder_directive_coder_supervisor_owner",
            "action": "RECONCILE_SHARED_DIRTY_CHECKOUT_WITH_CURRENT_FILE_OWNERS_THEN_RECHECK_SUPERVISOR",
            "requires": [
                "preserve_all_other_agents_edits",
                "confirm_directive_scope_and_owner",
                "review_implementation_ready_authority",
                "existing_worktree_or_clean_authorised_workspace",
            ],
            "automatic_enqueuing_authorized": False,
        },
    ]
    blockers = []
    if plan["recent_without_promotion_contract"] > 0:
        blockers.append("RECENT_PLAN_PROMOTION_CONTRACTS_ABSENT")
    if not plan_has_implement_contract:
        blockers.append("NO_STRUCTURALLY_COMPLETE_IMPLEMENT_CONTRACT_FOUND")
    if directives["implementation_ready"] and checkout["supervisor_dirty_checkout_gate"]:
        blockers.append("FOUNDER_SUPERVISOR_BLOCKED_BY_SHARED_DIRTY_CHECKOUT")
    if not directives["implementation_ready"]:
        blockers.append("NO_FOUNDER_DIRECTIVE_READY_FOR_IMPLEMENTATION")
    writer = probe_current_writer_provider(root)
    historical_warnings = []
    if failure_classes["model_or_provider"]:
        historical_warnings.append("HISTORICAL_IMPLEMENT_MODEL_PROVIDER_ERRORS_EXIST")
        next_actions.append({
            "owner": "existing_empire_coder_inference_reliability_owner",
            "action": "RECONCILE_HISTORIC_PROVIDER_FAILURES_WITH_CURRENT_LOCAL_ROUTE",
            "requires": [
                "inspect_original_private_failed_job_receipts",
                "confirm_existing_writer_endpoint_and_cooldown",
                "verify_real_authorized_patch_only_after_other_gates",
                "do_not_replay_prior_mutations_without_owner_approval",
            ],
            "automatic_enqueuing_authorized": False,
        })
    if not writer["active_writer_route_eligible"]:
        blockers.append("CURRENT_WRITER_MODEL_ROUTE_UNVERIFIED_OR_UNAVAILABLE")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "as_of_utc": current.isoformat(),
        "lookback_hours": lookback_hours,
        "canonical_job_files_examined": scanned,
        "recent_coder_job_counts": dict(sorted(recent.items())),
        "completed_plan_promotion_eligibility": dict(sorted(plan.items())),
        "founder_directive_state_counts": dict(sorted(directives.items())),
        "historical_implementation_failure_categories": dict(sorted(failure_classes.items())),
        "historical_warnings": historical_warnings,
        "current_writer_provider": writer,
        "canonical_checkout": checkout,
        "blockers": blockers,
        "required_existing_owner_actions": next_actions,
        "coder_implementation_automatically_started": False,
        "approval_inferred_from_plan": False,
        "contract_schema_check_not_execution_authorization": True,
        "external_task_or_contact_created": False,
        "real_business_records_modified": False,
        "engineering_uplift_measured": False,
    }
