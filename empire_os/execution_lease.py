"""Exclusive domain/path leases for EmpireOS mutating build workers."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from uuid import uuid4


PROTECTED_PREFIXES = (
    "recovery",
    "toop",
    "runtime",
    ".git",
)
PROTECTED_EXACT = {
    ".env",
    ".env.local",
    ".env.production",
}


class ExecutionLeaseError(RuntimeError):
    pass

# Root-controlled activation is deliberately absent in production until
# independent service-identity/issuer/protected-access acceptance is complete.
# A per-worker environment variable is NOT sufficient activation authority.
OWNER_LOCK_MARKER = Path("/etc/empire_os/owner_lock.enforced")


def owner_mutation_lock_active() -> bool:
    """Fail closed for any present or unreadable activation marker.

    This shared lease boundary catches direct original worker calls too.
    A missing root-owned marker preserves the existing original lease path.
    Only the original root-custodied release owner may activate or remove it.
    """
    path = OWNER_LOCK_MARKER
    try:
        folder = path.parent.lstat()
        if (
            not stat.S_ISDIR(folder.st_mode)
            or folder.st_uid != 0
            or folder.st_mode & 0o022
        ):
            raise ExecutionLeaseError("owner_lock_config_parent_untrusted")
        info = path.lstat()
    except FileNotFoundError as exc:
        if getattr(exc, "filename", None) == str(path):
            return False
        raise ExecutionLeaseError("owner_lock_config_parent_missing") from exc
    except OSError as exc:
        raise ExecutionLeaseError("owner_lock_config_unreadable") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or stat.S_IMODE(info.st_mode) != 0o644
        or info.st_nlink != 1
        or info.st_size != 8
    ):
        raise ExecutionLeaseError("owner_lock_config_custody_invalid")
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise ExecutionLeaseError("owner_lock_config_unreadable") from exc
    if value != b"ENFORCE\n":
        raise ExecutionLeaseError("owner_lock_config_invalid")
    return True




@dataclass(frozen=True)
class ExecutionLease:
    lease_id: str
    owner: str
    job_id: str
    resources: tuple[str, ...]
    acquired_at: str
    expires_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_resource(value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ExecutionLeaseError("lease resource required")
    if raw.startswith("domain:") or raw.startswith("surface:"):
        namespace, _, key = raw.partition(":")
        key = key.strip()
        if not key or "/" in key or ".." in key:
            raise ExecutionLeaseError("invalid logical lease resource")
        return f"{namespace}:{key}"

    if raw.startswith("path:"):
        raw = raw[5:]
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ExecutionLeaseError("unsafe lease path")
    clean = str(path)
    while clean.startswith("./"):
        clean = clean[2:]
    if not clean or clean == ".":
        raise ExecutionLeaseError("unsafe lease path")
    if clean in PROTECTED_EXACT:
        raise ExecutionLeaseError("protected path cannot be leased")
    first = clean.split("/", 1)[0]
    if first in PROTECTED_PREFIXES:
        raise ExecutionLeaseError("protected path cannot be leased")
    return f"path:{clean.rstrip('/')}"


def _path_overlap(left: str, right: str) -> bool:
    if not left.startswith("path:") or not right.startswith("path:"):
        return left == right
    a = left[5:].rstrip("/")
    b = right[5:].rstrip("/")
    return (
        a == b
        or a.startswith(b + "/")
        or b.startswith(a + "/")
    )


def resources_conflict(
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> bool:
    return any(_path_overlap(a, b) for a in left for b in right)


class ExecutionLeaseManager:
    def __init__(
        self,
        root: str | Path = "/srv/empire_os/runtime/execution_plane",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.state_path = self.root / "leases.json"
        self.lock_path = self.root / ".leases.lock"
        self.lock_path.touch(exist_ok=True)
        os.chmod(self.lock_path, 0o600)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self.lock_path.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _parse_ts(value: str) -> datetime | None:
        try:
            result = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)

    def _read(self) -> list[ExecutionLease]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = []
        rows = raw if isinstance(raw, list) else []
        leases: list[ExecutionLease] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                leases.append(
                    ExecutionLease(
                        lease_id=str(row["lease_id"]),
                        owner=str(row["owner"]),
                        job_id=str(row["job_id"]),
                        resources=tuple(
                            _normalise_resource(value)
                            for value in row.get("resources", [])
                        ),
                        acquired_at=str(row["acquired_at"]),
                        expires_at=str(row["expires_at"]),
                    )
                )
            except (KeyError, ExecutionLeaseError):
                continue
        return leases

    def _write(self, leases: list[ExecutionLease]) -> None:
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(
                [lease.as_dict() for lease in leases],
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(self.state_path)
        os.chmod(self.state_path, 0o600)

    def _prune(
        self,
        leases: list[ExecutionLease],
        *,
        now: datetime,
    ) -> list[ExecutionLease]:
        return [
            lease
            for lease in leases
            if (
                (expires := self._parse_ts(lease.expires_at))
                is not None
                and expires > now
            )
        ]

    def acquire(
        self,
        *,
        owner: str,
        job_id: str,
        resources: tuple[str, ...],
        ttl_seconds: int = 1800,
    ) -> ExecutionLease:
        clean_owner = str(owner or "").strip()
        clean_job = str(job_id or "").strip()
        if not clean_owner or not clean_job:
            raise ExecutionLeaseError("owner and job_id required")
        normalised = tuple(
            dict.fromkeys(_normalise_resource(value) for value in resources)
        )
        if not normalised:
            raise ExecutionLeaseError("at least one lease resource required")

        ttl = max(60, min(int(ttl_seconds), 7200))
        # Preserve original off-mode behaviour. With protected enforcement
        # active, direct acquire() can never impersonate a trusted signer;
        # only the separate signed-ticket adapter (under this SAME flock)
        # can grant a mutation lease after authenticated review.
        if owner_mutation_lock_active():
            # Original admission boundary; no separate worker, scheduler or
            # lease manager. Sealed founder credentials + real service UID
            # are required; missing custody is an explicit HOLD.
            from empire_os.agent_owner_authority_review import (
                OwnerAuthorityHold, acquire_sealed_owner_lease,
            )
            try:
                return acquire_sealed_owner_lease(
                    lease_manager=self, lease_owner=clean_owner,
                    job_id=clean_job, resources=normalised, ttl_seconds=ttl,
                )
            except OwnerAuthorityHold as exc:
                # Preserve existing Hermes/Pi/Coder error-handling contract.
                raise ExecutionLeaseError(
                    f"SIGNED_WORKSTREAM_TICKET_REQUIRED:{exc}"
                ) from exc
        now = _now()
        with self._locked():
            # Close the race with a concurrent root-controlled activation
            # while a mutation lease waits on another worker's flock.
            if owner_mutation_lock_active():
                raise ExecutionLeaseError("SIGNED_WORKSTREAM_TICKET_REQUIRED")
            active = self._prune(self._read(), now=now)
            for lease in active:
                if resources_conflict(normalised, lease.resources):
                    raise ExecutionLeaseError(
                        f"lease_conflict:{lease.owner}:{lease.job_id}"
                    )
            lease = ExecutionLease(
                lease_id=f"exec_lease_{uuid4().hex}",
                owner=clean_owner,
                job_id=clean_job,
                resources=normalised,
                acquired_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=ttl)).isoformat(),
            )
            active.append(lease)
            self._write(active)
            return lease

    def release(self, lease_id: str) -> bool:
        clean = str(lease_id or "").strip()
        if not clean:
            return False
        with self._locked():
            leases = self._read()
            kept = [lease for lease in leases if lease.lease_id != clean]
            changed = len(kept) != len(leases)
            if changed:
                self._write(kept)
            return changed

    def active(self) -> list[dict[str, Any]]:
        now = _now()
        with self._locked():
            active = self._prune(self._read(), now=now)
            self._write(active)
            return [lease.as_dict() for lease in active]


def attest_original_worker_proposal(
    *,
    lease_owner: str,
    job_id: str,
    trusted_worktree_root: Path,
    independently_observed_changed_paths: tuple[str, ...],
) -> None:
    """Original worker publication check; unchanged behaviour when OFF.

    A successful check is not a grant to merge, deploy or make external calls.
    """
    if not owner_mutation_lock_active():
        return
    from empire_os.agent_owner_authority_review import (
        OwnerAuthorityHold, attest_sealed_worker_proposal,
    )
    try:
        attest_sealed_worker_proposal(
            lease_owner=lease_owner, job_id=job_id,
            trusted_worktree_root=trusted_worktree_root,
            independently_observed_changed_paths=independently_observed_changed_paths,
        )
    except OwnerAuthorityHold as exc:
        raise ExecutionLeaseError(f"OWNER_PROPOSAL_SCOPE_BLOCKED:{exc}") from exc
