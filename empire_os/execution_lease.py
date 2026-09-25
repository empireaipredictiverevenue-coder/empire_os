"""Exclusive domain/path leases for EmpireOS mutating build workers."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
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
        now = _now()
        with self._locked():
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
