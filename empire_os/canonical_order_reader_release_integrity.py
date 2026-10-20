"""Fail-closed, original-owner Git release-integrity observer for verified orders.

This only compares checked-in source against its runtime file, then checks the
canonical reader entrypoint. It never authenticates an individual order, tenant,
database privilege or owner sign-off. No mutations, network or new agent jobs.
"""
from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path
import subprocess

SCHEMA = "empire.commercial.canonical_reader_release_integrity.v1"
SOURCE = "empire_os/execution_bus_data_repository.py"
MAX_FILE_BYTES = 250_000
GIT_TIMEOUT_SECONDS = 4


def _owner_method_in_source(raw: bytes) -> bool:
    tree = ast.parse(raw.decode("utf-8"))
    methods = [
        method
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ExecutionBusDataRepository"
        for method in node.body
        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        and method.name == "verified_outcome_feedback"
    ]
    if len(methods) != 1 or not isinstance(methods[0], ast.FunctionDef):
        return False
    args = methods[0].args
    expected = {"self", "fulfilment_order_id", "tenant_id", "repo_root", "as_of"}
    present = {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    return expected.issubset(present)


def inspect_canonical_reader_release_integrity(repo_root: Path) -> dict:
    """Inspect exact allowlisted owner file at HEAD, not arbitrary owner paths."""
    status = "ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN"
    file_matches = False
    method_checked_in = False
    method_visible = False
    checked_in_sha = None
    working_sha = None
    try:
        from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
        method_visible = callable(getattr(
            ExecutionBusDataRepository, "verified_outcome_feedback", None
        ))
        root = Path(repo_root).resolve(strict=True)
        path = root / SOURCE
        if path.is_symlink() or not path.is_file():
            raise ValueError("canonical owner source file unavailable")
        stat = path.stat()
        if not 0 < stat.st_size <= MAX_FILE_BYTES:
            raise ValueError("canonical owner file exceeds bound")
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("canonical owner input too large")
        # Check that the declared root is genuinely its own Git worktree.
        info = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, check=True, timeout=GIT_TIMEOUT_SECONDS,
        )
        if Path(info.stdout.decode("utf-8").strip()).resolve() != root:
            raise ValueError("not exact canonical owner git worktree")
        committed = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:" + SOURCE],
            capture_output=True, check=True, timeout=GIT_TIMEOUT_SECONDS,
        ).stdout
        if not 0 < len(committed) <= MAX_FILE_BYTES:
            raise ValueError("invalid committed owner source size")
        working_sha = sha256(raw).hexdigest()
        checked_in_sha = sha256(committed).hexdigest()
        file_matches = working_sha == checked_in_sha
        method_checked_in = _owner_method_in_source(committed)
        if not file_matches:
            status = "ORIGINAL_OWNER_SOURCE_DIRTY_RELEASE_HOLD"
        elif not method_checked_in:
            status = "VERIFIED_ORDER_READER_NOT_COMMITTED"
        elif not method_visible:
            status = "COMMITTED_OWNER_READER_NOT_LOADED"
        else:
            status = "COMMITTED_READER_PRESENT_OWNER_APPROVAL_REQUIRED"
    except (OSError, ValueError, UnicodeError, SyntaxError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "owner_source_file_matches_committed_head": file_matches,
        "verified_outcome_reader_method_checked_in": method_checked_in,
        "reader_callable_in_running_process": method_visible,
        "checked_in_owner_source_sha256": checked_in_sha,
        "runtime_owner_source_sha256": working_sha,
        "original_owner_release_attested": False,
        "actual_canonical_order_read_performed": False,
        "tenant_privileges_proven": False,
        "verified_buyer_orders": None,
        "realized_revenue_cents": None,
        "method_presence_not_commercial_authority": True,
        "next_existing_owner": "execution_bus_data_repository",
        "outbound_authorized": False,
        "payment_execution": False,
        "database_writes": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }


def review_reader_release_transition(
    previous: dict | None,
    current: dict,
    previous_transition: dict | None = None,
) -> dict:
    """Debounce transitory Git/source unavailability without upgrading proof.

    Memory of the last confirmed allowlisted state survives an unavailable
    observation. It is a comparison checkpoint only, never current authority.
    """
    unknown = "ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN"
    statuses = {
        unknown,
        "ORIGINAL_OWNER_SOURCE_DIRTY_RELEASE_HOLD",
        "VERIFIED_ORDER_READER_NOT_COMMITTED",
        "COMMITTED_OWNER_READER_NOT_LOADED",
        "COMMITTED_READER_PRESENT_OWNER_APPROVAL_REQUIRED",
    }

    def trusted(value):
        return (
            isinstance(value, dict)
            and value.get("schema_version") == SCHEMA
            and value.get("status") in statuses
            and value.get("execution_authority") == "none"
            and value.get("database_writes") is False
            and value.get("outbound_authorized") is False
            and value.get("payment_execution") is False
            and value.get("agent_tasks_created") is False
            and value.get("original_owner_release_attested") is False
        )

    if not trusted(current):
        raise ValueError("trusted canonical owner release-integrity proof required")
    prior_status = previous["status"] if trusted(previous) else None
    last_known = prior_status if prior_status != unknown else None
    valid_prior_transition = (
        isinstance(previous_transition, dict)
        and previous_transition.get("schema_version") ==
        "empire.commercial.canonical_reader_release_transition.v1"
        and previous_transition.get("mode") == "OBSERVE"
        and previous_transition.get("execution_authority") == "none"
        and previous_transition.get("database_writes") is False
        and previous_transition.get("outbound_authorized") is False
        and previous_transition.get("new_agent_created") is False
        and previous_transition.get("current_allowlisted_owner_state") == prior_status
        and previous_transition.get("last_confirmed_original_owner_state") in (
            statuses - {unknown}
        ) | {None}
    )
    if valid_prior_transition:
        last_known = previous_transition["last_confirmed_original_owner_state"]
    after = current["status"]
    if after == unknown:
        state = "ORIGINAL_OWNER_SOURCE_TEMPORARILY_UNAVAILABLE_HOLD_NO_REVIEW"
        review = False
    elif last_known is None:
        state = "FIRST_ORIGINAL_OWNER_RELEASE_INTEGRITY_CHECK"
        review = False
    elif last_known == after:
        state = "UNCHANGED_ORIGINAL_OWNER_RELEASE_HOLD"
        review = False
    else:
        state = "ORIGINAL_OWNER_RELEASE_INTEGRITY_CHANGED_REVIEW_REQUIRED"
        review = True

    return {
        "schema_version": "empire.commercial.canonical_reader_release_transition.v1",
        "mode": "OBSERVE",
        "status": state,
        "previous_allowlisted_owner_state": prior_status,
        "current_allowlisted_owner_state": after,
        "last_confirmed_original_owner_state": (
            last_known if after == unknown else after
        ),
        "transient_source_error_does_not_create_owner_job": after == unknown,
        "existing_owner_review_eligible": review,
        "new_agent_created": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
