"""Private owner-authority preflight for the ORIGINAL EmpireOS execution plane.

Candidate only: no issuer, deployment, agent, timer, or external action.
Only a trusted founder-policy signer can establish standing owners. Worker-
supplied labels and temporary execution leases NEVER confer ownership.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from empire_os.execution_lease import (
    ExecutionLease, ExecutionLeaseManager, _normalise_resource, resources_conflict,
)

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

POLICY_SCHEMA = "empire.execution.owner_policy.v1"
TICKET_SCHEMA = "empire.execution.owner_ticket.v1"
_ID = re.compile(r"[a-z][a-z0-9_-]{1,80}\Z")


class OwnerAuthorityHold(ValueError):
    """Hold a mutation without falling back to self-assigned authority."""


def _id(v: Any) -> str:
    if not isinstance(v, str) or not _ID.fullmatch(v):
        raise OwnerAuthorityHold("INVALID_OWNER_OR_DOMAIN_ID")
    return v


def _path(v: Any) -> str:
    if not isinstance(v, str) or len(v) > 300 or not v:
        raise OwnerAuthorityHold("INVALID_PATH")
    if (
        v.startswith(("/", "~")) or "\\" in v or "//" in v
        or v.endswith("/") or any(ord(char) < 32 or ord(char) == 127 for char in v)
    ):
        raise OwnerAuthorityHold("UNSAFE_PATH")
    parts = v.split("/")
    if any(
        p in (".", "..", "", ".git")
        or p == ".env" or p.startswith(".env.")
        for p in parts
    ):
        raise OwnerAuthorityHold("UNSAFE_PATH")
    if parts[0] in ("runtime", "recovery", "toop") or parts[0].startswith("."):
        raise OwnerAuthorityHold("PROTECTED_PATH")
    return v


def _prefix(parent: str, child: str) -> bool:
    return parent == child or child.startswith(parent + "/")


def _timestamp(v: Any) -> datetime:
    if not isinstance(v, str) or len(v) > 45:
        raise OwnerAuthorityHold("INVALID_CLOCK")
    try:
        t = datetime.fromisoformat(v)
    except (ValueError, OverflowError) as exc:
        raise OwnerAuthorityHold("INVALID_CLOCK") from exc
    if t.utcoffset() is None:
        raise OwnerAuthorityHold("NAIVE_CLOCK")
    return t.astimezone(timezone.utc)


def _verify_signed(obj: Mapping[str, Any], *, public_key: Ed25519PublicKey) -> dict:
    if not isinstance(obj, Mapping) or not isinstance(obj.get("signature"), str):
        raise OwnerAuthorityHold("MISSING_SIGNED_AUTHORITY")
    try:
        signature = bytes.fromhex(obj["signature"])
        data = {k: v for k, v in obj.items() if k != "signature"}
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")
        public_key.verify(signature, encoded)
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise OwnerAuthorityHold("AUTHORITY_SIGNATURE_INVALID") from exc
    return data


def _unique_paths(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 50:
        raise OwnerAuthorityHold("NO_BOUNDED_PATH_SCOPE")
    paths = tuple(_path(v) for v in value)
    if len(set(paths)) != len(paths):
        raise OwnerAuthorityHold("DUPLICATE_PATH")
    return paths

def verify_owner_mutation(
    *,
    signed_policy: Mapping[str, Any],
    signed_ticket: Mapping[str, Any],
    trusted_founder_public_key: Ed25519PublicKey,
    trusted_policy_sha256: str,
    authenticated_worker_principal: str,
    request_job_id: str,
    request_department: str,
    request_capability: str,
    changed_paths: tuple[str, ...],
    lease_resources: tuple[str, ...],
    now: datetime,
) -> dict[str, Any]:
    """Check exactly one mutating request before the EXISTING lease manager.

    The caller MUST source the founder public key from trusted custody and the
    principal from authenticated worker identity, never the worker's payload.
    Approval here does not replace a lease or any production release gate.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise OwnerAuthorityHold("CLOCK_REQUIRED")
    at = now.astimezone(timezone.utc)
    if not isinstance(trusted_policy_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", trusted_policy_sha256):
        raise OwnerAuthorityHold("NO_PINNED_FOUNDER_POLICY")
    try:
        raw_policy = json.dumps(signed_policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")
    except (TypeError, ValueError) as exc:
        raise OwnerAuthorityHold("INVALID_FOUNDER_POLICY_PAYLOAD") from exc
    if hashlib.sha256(raw_policy).hexdigest() != trusted_policy_sha256:
        raise OwnerAuthorityHold("STALE_OR_REVOKED_OWNER_POLICY")
    policy = _verify_signed(signed_policy, public_key=trusted_founder_public_key)
    ticket = _verify_signed(signed_ticket, public_key=trusted_founder_public_key)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise OwnerAuthorityHold("OWNER_POLICY_NOT_CANONICAL")
    if ticket.get("schema_version") != TICKET_SCHEMA:
        raise OwnerAuthorityHold("OWNER_TICKET_NOT_CANONICAL")
    if policy.get("issuer") != "FOUNDER_CONTROLLED_EXECUTION_OWNER":
        raise OwnerAuthorityHold("UNKNOWN_OWNER_ISSUER")
    if ticket.get("authority") != "internal_write":
        raise OwnerAuthorityHold("NO_INTERNAL_WRITE_TICKET")

    issued = _timestamp(ticket.get("issued_at"))
    expires = _timestamp(ticket.get("expires_at"))
    if issued > at + timedelta(seconds=90) or at >= expires or issued > at:
        raise OwnerAuthorityHold("TICKET_NOT_CURRENT")
    if expires - issued > timedelta(hours=2) or expires <= issued:
        raise OwnerAuthorityHold("TICKET_LIFETIME_INVALID")
    if ticket.get("job_id") != request_job_id or not request_job_id:
        raise OwnerAuthorityHold("JOB_ID_MISMATCH")
    if ticket.get("department") != request_department or not request_department:
        raise OwnerAuthorityHold("DEPARTMENT_MISMATCH")
    if ticket.get("capability") != request_capability or not request_capability:
        raise OwnerAuthorityHold("CAPABILITY_MISMATCH")
    principal = _id(authenticated_worker_principal)
    if _id(ticket.get("principal")) != principal:
        raise OwnerAuthorityHold("SPOOFED_WORKER_OWNER")
    assignment_id = _id(ticket.get("assignment_id"))
    _id(ticket.get("ticket_id"))  # Signed one-use identity from the trusted issuer.

    assignments = policy.get("assignments")
    if not isinstance(assignments, list) or not 1 <= len(assignments) <= 100:
        raise OwnerAuthorityHold("NO_APPROVED_WORKSTREAMS")
    seen_ids: set[str] = set()
    scopes: list[tuple[str, str]] = []
    chosen = None
    for row in assignments:
        if not isinstance(row, dict) or row.get("approved") is not True:
            raise OwnerAuthorityHold("UNAPPROVED_WORKSTREAM")
        aid = _id(row.get("assignment_id"))
        _id(row.get("principal"))
        if aid in seen_ids:
            raise OwnerAuthorityHold("DUPLICATE_WORKSTREAM_OWNER")
        seen_ids.add(aid)
        if not isinstance(row.get("department"), str) or not row["department"]:
            raise OwnerAuthorityHold("OWNER_DEPARTMENT_UNVERIFIED")
        paths = _unique_paths(row.get("allowed_paths"))
        caps = row.get("capabilities")
        domains = row.get("allowed_domains")
        if not isinstance(caps, list) or not caps or not all(isinstance(v, str) for v in caps):
            raise OwnerAuthorityHold("OWNER_CAPABILITY_UNVERIFIED")
        if not isinstance(domains, list) or not all(isinstance(v, str) and _ID.fullmatch(v) for v in domains):
            raise OwnerAuthorityHold("OWNER_DOMAINS_UNVERIFIED")
        if not isinstance(row.get("founder_decision_ref"), str) or not row["founder_decision_ref"]:
            raise OwnerAuthorityHold("NO_FOUNDER_ASSIGNMENT_RECEIPT")
        scopes.extend((aid, p) for p in paths)
        if aid == assignment_id:
            chosen = row
    for i, (left_id, left_path) in enumerate(scopes):
        for right_id, right_path in scopes[i + 1:]:
            if left_id != right_id and (_prefix(left_path, right_path) or _prefix(right_path, left_path)):
                raise OwnerAuthorityHold("OVERLAPPING_WORKSTREAM_ASSIGNMENTS")
    if chosen is None:
        raise OwnerAuthorityHold("UNKNOWN_WORKSTREAM")
    if (
        chosen["principal"] != principal
        or chosen["department"] != request_department
        or request_capability not in chosen["capabilities"]
        or chosen["founder_decision_ref"] != ticket.get("founder_decision_ref")
    ):
        raise OwnerAuthorityHold("WORKSTREAM_NOT_ASSIGNED_TO_REQUESTER")

    targets = tuple(_path(p) for p in changed_paths)
    signed_paths = _unique_paths(ticket.get("changed_paths"))
    if not targets or targets != signed_paths:
        raise OwnerAuthorityHold("UNSIGNED_OR_CHANGED_FILE_SET")
    if not all(any(_prefix(p, t) for p in chosen["allowed_paths"]) for t in targets):
        raise OwnerAuthorityHold("CROSS_AGENT_FILE_CHANGE")
    signed_leases = ticket.get("lease_resources")
    if not isinstance(signed_leases, list) or not lease_resources or tuple(signed_leases) != lease_resources:
        raise OwnerAuthorityHold("LEASE_NOT_BOUND_TO_OWNER_TICKET")
    if not {f"path:{p}" for p in targets}.issubset(set(lease_resources)):
        raise OwnerAuthorityHold("CHANGED_FILES_NOT_FULLY_LEASED")
    for resource in lease_resources:
        if not isinstance(resource, str):
            raise OwnerAuthorityHold("BAD_LEASE_RESOURCE")
        if resource.startswith("path:"):
            path = _path(resource[5:])
            if not any(_prefix(p, path) for p in chosen["allowed_paths"]):
                raise OwnerAuthorityHold("CROSS_AGENT_LEASE_SCOPE")
        elif resource.startswith("domain:"):
            if resource[7:] not in chosen["allowed_domains"]:
                raise OwnerAuthorityHold("UNAPPROVED_LOGICAL_DOMAIN")
        else:
            raise OwnerAuthorityHold("UNSUPPORTED_RESOURCE_CLASS")
    return {
        "status": "FOUNDER_OWNER_SCOPE_VALIDATED_BEFORE_LEASE",
        "assignment_id": assignment_id,
        "principal": principal,
        "request_job_id": request_job_id,
        "verified_path_count": len(targets),
        "existing_execution_lease_still_required": True,
        "production_release_authorized": False,
        "external_actions_authorized": False,
        "payment_actions_authorized": False,
    }


def acquire_owner_authorized_lease(
    *,
    lease_manager: Any,
    signed_policy: Mapping[str, Any],
    signed_ticket: Mapping[str, Any],
    trusted_founder_public_key: Ed25519PublicKey,
    trusted_policy_sha256: str,
    authenticated_worker_principal: str,
    request_job_id: str,
    request_department: str,
    request_capability: str,
    changed_paths: tuple[str, ...],
    lease_resources: tuple[str, ...],
    now: datetime,
    ttl_seconds: int = 1200,
) -> Any:
    """Private adapter using the EXISTING lease manager, not a second lock.

    The original trusted execution-plane owner must bind the verified service
    identity, pinned key and policy digest, and mandate this path for ALL
    mutating workers before enabling it. Do not import for live work until
    original-owner integration/rollback and founder assignments are approved.
    """
    review = verify_owner_mutation(
        signed_policy=signed_policy,
        signed_ticket=signed_ticket,
        trusted_founder_public_key=trusted_founder_public_key,
        trusted_policy_sha256=trusted_policy_sha256,
        authenticated_worker_principal=authenticated_worker_principal,
        request_job_id=request_job_id,
        request_department=request_department,
        request_capability=request_capability,
        changed_paths=changed_paths,
        lease_resources=lease_resources,
        now=now,
    )
    # Never grant an operational lease longer than the signed job ticket.
    # The existing lease manager clamps TTL values to [60, 7200], so reject
    # out-of-bounds requests here instead of silently expanding authority.
    if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 7200:
        raise OwnerAuthorityHold("OWNER_LEASE_TTL_OUT_OF_BOUNDS")
    expires_at = _timestamp(signed_ticket.get("expires_at"))
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise OwnerAuthorityHold("CLOCK_REQUIRED")
    time_remaining = (expires_at - now.astimezone(timezone.utc)).total_seconds()
    if ttl_seconds > time_remaining:
        raise OwnerAuthorityHold("OWNER_LEASE_OUTLIVES_SIGNED_TICKET")
    if type(lease_manager) is not ExecutionLeaseManager:
        raise OwnerAuthorityHold("TRUSTED_ORIGINAL_LEASE_MANAGER_REQUIRED")
    path = _ticket_receipt_path(lease_manager)
    ticket_id = _id(signed_ticket.get("ticket_id"))
    ticket_digest = hashlib.sha256(("empire-owner-ticket-v1:" + ticket_id).encode("ascii")).hexdigest()
    # The ORIGINAL manager's lock serializes the replay check and lease state;
    # no second manager, process, database, scheduler or competing lock.
    with lease_manager._locked():
        actual_now = datetime.now(timezone.utc)
        if abs((actual_now - now.astimezone(timezone.utc)).total_seconds()) > 90:
            raise OwnerAuthorityHold("TRUSTED_JOB_CLOCK_STALE")
        if not _timestamp(signed_ticket.get("issued_at")) <= actual_now < expires_at:
            raise OwnerAuthorityHold("OWNER_TICKET_NOT_LIVE_AT_LEASE_ACQUISITION")
        if ttl_seconds > (expires_at - actual_now).total_seconds():
            raise OwnerAuthorityHold("OWNER_LEASE_OUTLIVES_SIGNED_TICKET")
        consumed = _read_consumptions(path)
        if ticket_digest in consumed:
            raise OwnerAuthorityHold("SIGNED_OWNER_TICKET_ALREADY_CONSUMED")
        if len(consumed) >= MAX_CONSUMED_TICKETS:
            raise OwnerAuthorityHold("TICKET_RECEIPT_CAPACITY_REVIEW_REQUIRED")
        # Original manager historically skips malformed rows. The protected
        # owner adapter refuses corrupt live state instead of treating it as
        # free capacity for a second worker.
        state = lease_manager.state_path
        if state.exists() or state.is_symlink():
            try:
                metadata = state.lstat()
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise OwnerAuthorityHold("ORIGINAL_LEASE_STATE_CUSTODY_UNSAFE")
                raw_leases = json.loads(state.read_text(encoding="utf8"))
                if not isinstance(raw_leases, list):
                    raise OwnerAuthorityHold("ORIGINAL_LEASE_STATE_CORRUPT")
            except (OSError, TypeError, ValueError) as exc:
                raise OwnerAuthorityHold("ORIGINAL_LEASE_STATE_UNREADABLE") from exc
        else:
            raw_leases = []
        parsed = lease_manager._read()
        if len(parsed) != len(raw_leases):
            raise OwnerAuthorityHold("ORIGINAL_LEASE_STATE_PARTIALLY_INVALID")
        normalized = tuple(dict.fromkeys(_normalise_resource(r) for r in lease_resources))
        if len(normalized) != len(lease_resources):
            raise OwnerAuthorityHold("DUPLICATE_MUTATION_LEASE_RESOURCE")
        active = lease_manager._prune(parsed, now=actual_now)
        if any(resources_conflict(normalized, lease.resources) for lease in active):
            raise OwnerAuthorityHold("ORIGINAL_EXECUTION_LEASE_CONFLICT")
        lease = ExecutionLease(
            lease_id="exec_lease_" + uuid4().hex,
            owner=review["principal"], job_id=review["request_job_id"],
            resources=normalized,
            acquired_at=actual_now.isoformat(),
            expires_at=(actual_now + timedelta(seconds=ttl_seconds)).isoformat(),
        )
        # Persist the one-use receipt BEFORE committing the lease. A crash
        # between writes may burn a ticket, but cannot allow replay. The
        # original owner must reconcile burnt tickets via a fresh signed ID.
        _persist_consumptions(path, [*consumed, ticket_digest])
        lease_manager._write([*active, lease])
        return lease


def attest_actual_worktree_changes(
    *,
    trusted_worktree_root: Path,
    signed_changed_paths: tuple[str, ...],
    independently_observed_changed_paths: tuple[str, ...],
) -> dict[str, Any]:
    """Post-worktree *additional* check, not a substitute for signed authority.

    The original owner MUST derive independently_observed_changed_paths from
    trusted Git/worktree readback, not from a worker assertion. This rejects
    symlinks or hard-linked paths that could escape the authorised source lane.
    Deletions/renames need a separate owner-reviewed contract, not a bypass.
    """
    if (
        not isinstance(trusted_worktree_root, Path)
        or trusted_worktree_root.is_symlink()
        or not trusted_worktree_root.is_dir()
    ):
        raise OwnerAuthorityHold("UNTRUSTED_WORKTREE_ROOT")
    root = trusted_worktree_root.resolve(strict=True)
    signed = tuple(_path(p) for p in signed_changed_paths)
    observed = tuple(_path(p) for p in independently_observed_changed_paths)
    if not signed or len(set(signed)) != len(signed) or signed != observed:
        raise OwnerAuthorityHold("ACTUAL_CHANGES_NOT_EQUAL_TO_SIGNED_FILES")
    for relpath in observed:
        candidate = root
        for segment in relpath.split("/"):
            candidate = candidate / segment
            if candidate.is_symlink():
                raise OwnerAuthorityHold("SYMLINKED_CHANGED_PATH_DENIED")
            if not candidate.exists():
                raise OwnerAuthorityHold("MISSING_CHANGED_PATH_REQUIRES_OWNER_REVIEW")
        try:
            metadata = candidate.lstat()
        except OSError as exc:
            raise OwnerAuthorityHold("UNREADABLE_CHANGED_PATH") from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise OwnerAuthorityHold("NONREGULAR_CHANGED_FILE_DENIED")
        if metadata.st_nlink != 1:
            raise OwnerAuthorityHold("HARDLINKED_CHANGED_FILE_DENIED")
        if candidate.resolve(strict=True) != root / relpath:
            raise OwnerAuthorityHold("OUTSIDE_TRUSTED_WORKTREE")
    return {
        "status": "ORIGINAL_OWNER_WORKTREE_PATH_ATTESTED",
        "path_count": len(observed),
        "production_publication_authorized": False,
        "no_untrusted_worktree_paths": True,
    }


# This subordinate replay receipt uses the ORIGINAL lease manager's exclusive
# flock. It is a review-only candidate; the original execution-plane owner
# must independently accept its private API coupling, file custody and
# rollback rules before any production installation.
TICKET_RECEIPT_SCHEMA = "empire.execution.owner_ticket_consumption.v1"
TICKET_RECEIPT_NAME = ".owner_ticket_consumption.json"
MAX_CONSUMED_TICKETS = 4096


def _ticket_receipt_path(lease_manager: Any) -> Path:
    root = getattr(lease_manager, "root", None)
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise OwnerAuthorityHold("UNTRUSTED_ORIGINAL_LEASE_ROOT")
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise OwnerAuthorityHold("UNSAFE_ORIGINAL_LEASE_ROOT_PERMISSIONS")
    return root / TICKET_RECEIPT_NAME


def _read_consumptions(path: Path) -> list[str]:
    """Missing, corrupt or unsafe custody is a HOLD, never a clean slate."""
    try:
        metadata = path.lstat()
        if (not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid()
                or not 50 <= metadata.st_size <= 400_000):
            raise OwnerAuthorityHold("UNSAFE_TICKET_RECEIPT_CUSTODY")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "consumed"}:
            raise OwnerAuthorityHold("INVALID_TICKET_RECEIPT_SCHEMA")
        if raw["schema_version"] != TICKET_RECEIPT_SCHEMA:
            raise OwnerAuthorityHold("INVALID_TICKET_RECEIPT_SCHEMA")
        tokens = raw["consumed"]
        if (not isinstance(tokens, list) or len(tokens) > MAX_CONSUMED_TICKETS
                or any(not isinstance(x, str) or not re.fullmatch(r"[0-9a-f]{64}", x)
                       for x in tokens)
                or len(set(tokens)) != len(tokens)):
            raise OwnerAuthorityHold("INVALID_TICKET_RECEIPT_CONTENTS")
        return tokens
    except OwnerAuthorityHold:
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise OwnerAuthorityHold("TICKET_RECEIPT_MISSING_OR_UNREADABLE") from exc


def _persist_consumptions(path: Path, consumed: list[str]) -> None:
    """Only while the original lease manager's exclusive lock is held."""
    if len(consumed) > MAX_CONSUMED_TICKETS:
        raise OwnerAuthorityHold("TICKET_RECEIPT_CAPACITY_REVIEW_REQUIRED")
    content = json.dumps(
        {"schema_version": TICKET_RECEIPT_SCHEMA, "consumed": consumed},
        sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    name = path.with_name(".owner_ticket_receipt_stage_" + uuid4().hex)
    fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if name.exists():
            name.unlink()


def provision_owner_ticket_receipts_for_review(lease_manager: Any) -> Path:
    """Explicit *offline/test* provisioning only, not a live auto-initializer.

    The original owner must securely provision a protected receipt once and
    attest its custody. Deleting it never silently resets used ticket IDs.
    """
    path = _ticket_receipt_path(lease_manager)
    with lease_manager._locked():
        if path.exists() or path.is_symlink():
            raise OwnerAuthorityHold("EXISTING_TICKET_RECEIPT_CANNOT_BE_RESET")
        # O_EXCL ensures two initializers cannot replace a live receipt.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(json.dumps(
                    {"schema_version": TICKET_RECEIPT_SCHEMA, "consumed": []},
                    separators=(",", ":")
                ).encode("utf-8") + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return path
