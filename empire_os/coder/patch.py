"""Surgical patching with read-before-write and rollback checkpoints."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .policy import PolicyError, resolve_path, resolve_runtime_root, resolve_workspace


class PatchError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PatchEngine:
    def __init__(
        self,
        workspace: str | Path,
        *,
        runtime_root: str | Path | None = None,
    ) -> None:
        self.workspace = resolve_workspace(workspace)
        self.runtime_root = resolve_runtime_root(
            self.workspace, runtime_root
        )
        self.checkpoints = self.runtime_root / "checkpoints"
        self.checkpoints.mkdir(parents=True, exist_ok=True)
        self._read: set[Path] = set()

    def read(self, path: str) -> str:
        target = resolve_path(self.workspace, path)
        data = target.read_text(encoding="utf-8")
        self._read.add(target)
        return data

    def replace_exact(
        self,
        task_id: str,
        path: str,
        old: str,
        new: str,
        *,
        expected_count: int = 1,
    ) -> dict[str, str]:
        target = resolve_path(self.workspace, path)
        if target not in self._read:
            raise PatchError("read-before-write guard blocked patch")
        source = target.read_text(encoding="utf-8")
        count = source.count(old)
        if count != expected_count:
            raise PatchError(
                f"expected {expected_count} exact matches, found {count}"
            )
        self._checkpoint(task_id, target, source.encode("utf-8"))
        updated = source.replace(old, new, expected_count)
        self._atomic_write(target, updated)
        return {
            "path": str(target.relative_to(self.workspace)),
            "before_sha256": _sha256(source.encode("utf-8")),
            "after_sha256": _sha256(updated.encode("utf-8")),
        }

    def create_file(
        self,
        task_id: str,
        path: str,
        content: str,
    ) -> dict[str, str | None]:
        target = resolve_path(
            self.workspace, path, allow_missing=True
        )
        if target.exists():
            raise PatchError("create_file refuses to overwrite existing file")
        parent = target.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=False)
        self._checkpoint_marker(task_id, target)
        self._atomic_write(target, content)
        return {
            "path": str(target.relative_to(self.workspace)),
            "before_sha256": None,
            "after_sha256": _sha256(content.encode("utf-8")),
        }

    def rollback(self, task_id: str) -> list[str]:
        task_root = self._task_checkpoint_root(task_id)
        if not task_root.exists():
            return []
        restored: list[str] = []
        for marker in sorted(task_root.rglob("*.new")):
            rel = marker.relative_to(task_root).with_suffix("")
            target = resolve_path(
                self.workspace, rel, allow_missing=True
            )
            if target.exists():
                target.unlink()
            restored.append(str(rel))
        for snapshot in sorted(task_root.rglob("*.bak")):
            rel = snapshot.relative_to(task_root).with_suffix("")
            target = resolve_path(
                self.workspace, rel, allow_missing=True
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot, target)
            restored.append(str(rel))
        return restored

    def _checkpoint(
        self, task_id: str, target: Path, data: bytes
    ) -> None:
        rel = target.relative_to(self.workspace)
        snapshot = self._task_checkpoint_root(task_id) / rel
        backup = snapshot.with_suffix(snapshot.suffix + ".bak")
        if backup.exists():
            return
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(data)
        os.chmod(backup, 0o600)

    def _checkpoint_marker(self, task_id: str, target: Path) -> None:
        rel = target.relative_to(self.workspace)
        marker = (
            self._task_checkpoint_root(task_id) / rel
        ).with_suffix(target.suffix + ".new")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("created\n", encoding="utf-8")
        os.chmod(marker, 0o600)

    def _task_checkpoint_root(self, task_id: str) -> Path:
        safe = "".join(
            ch for ch in task_id if ch.isalnum() or ch in "_-"
        )
        if safe != task_id or not safe:
            raise PatchError("invalid task id")
        return self.checkpoints / safe

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        tmp = path.with_name(path.name + ".empire-coder.tmp")
        tmp.write_text(content, encoding="utf-8")
        mode = path.stat().st_mode if path.exists() else 0o100644
        os.chmod(tmp, mode & 0o777)
        tmp.replace(path)
