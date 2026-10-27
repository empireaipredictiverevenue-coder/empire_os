"""Read-only acceptance inventory for the ORIGINAL Agent & Tool Execution Plane.

Static source inspection is evidence of missing adoption, NOT proof of security
when a string or wrapper exists. Does not modify workers, leases, policy or
systemd; never promotes the private candidate to production authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

ENTRY_POINTS = {
    "hermes": "empire_os/hermes_control.py",
    "pi": "empire_os/pi_sandbox_runner.py",
    "empire_coder_sandbox": "empire_os/empire_coder_sandbox_runner.py",
    "empire_coder_worker": "empire_os/coder/worker.py",
}
DIRECT_LEASE = re.compile(r"(?:lease_manager|manager|self\._execution_lease_manager\(\))\.acquire\s*\(")
REGISTER = "docs/handoffs/FOUNDER_WORKSTREAM_OWNER_REGISTER_DRAFT_20261027.json"


def _bounded_file(path: Path, limit: int) -> str | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def inspect_original_owner_integration(root: Path) -> dict[str, Any]:
    """Never return production enforcement=PASS from source scanning alone."""
    root = Path(root)
    rows = []
    for name, relpath in ENTRY_POINTS.items():
        raw = _bounded_file(root / relpath, 2_000_000)
        rows.append({
            "worker": name,
            "source_file": relpath,
            "readable_source": raw is not None,
            "original_direct_lease_call_observed": (
                bool(DIRECT_LEASE.search(raw)) if raw is not None else None
            ),
            "signed_owner_adapter_reference_observed": (
                "acquire_owner_authorized_lease(" in raw if raw is not None else False
            ),
            "independent_owner_approval_verified": False,
        })
    draft_raw = _bounded_file(root / REGISTER, 80_000)
    approved_count = None
    verified_principals = None
    draft_safe = False
    if draft_raw is not None:
        try:
            draft = json.loads(draft_raw)
            rows_draft = draft.get("candidate_assignments")
            if (
                draft.get("schema_version")
                == "empire.execution.owner_register_review_draft.v1"
                and isinstance(rows_draft, list) and len(rows_draft) <= 50
            ):
                approved_count = sum(x.get("approved") is True for x in rows_draft if isinstance(x, dict))
                verified_principals = sum(
                    bool(x.get("authenticated_principal"))
                    for x in rows_draft if isinstance(x, dict)
                )
                draft_safe = draft.get("policy_signed") is False and draft.get("production_enforcement_enabled") is False
        except (ValueError, AttributeError, TypeError):
            pass
    missing = [x["worker"] for x in rows if not x["readable_source"]]
    direct = [x["worker"] for x in rows if x["original_direct_lease_call_observed"] is True]
    return {
        "schema_version": "empire.execution.owner_integration_readiness.v1",
        "status": "ORIGINAL_OWNER_INTEGRATION_HOLD",
        "mode": "READ_ONLY_STATIC_ADOPTION_CHECK",
        "worker_entry_points": rows,
        "unreadable_worker_sources": missing,
        "direct_lease_entry_points": direct,
        "founder_draft_present_unapproved": draft_safe,
        "draft_approved_owner_count": approved_count,
        "draft_authenticated_principal_count": verified_principals,
        "sealed_policy_verified": False,
        "trusted_worker_identity_binding_verified": False,
        "ticket_replay_protection_verified": False,
        "direct_shell_plugin_write_boundary_verified": False,
        "production_enforcement_verified": False,
        "production_write_performed": False,
        "agent_reassigned": False,
        "new_timer_created": False,
        "next_action": "ORIGINAL_EXECUTION_OWNER_REVIEW_AND_ATTEST_BEFORE_GUARDED_RELEASE",
    }
