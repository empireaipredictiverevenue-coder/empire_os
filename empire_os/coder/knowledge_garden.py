"""Knowledge-base gardening for Empire Coder.

Original source files are never deleted. The garden builds a reviewed manifest
that retrieval can use to prefer canonical, fresh, non-duplicate engineering
knowledge and quarantine stale or contradictory legacy material.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .models import utc_now
from .policy import resolve_runtime_root, resolve_workspace


class KnowledgeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    QUARANTINED = "QUARANTINED"


class KnowledgeKind(str, Enum):
    CANONICAL = "canonical"
    CURATED_SKILL = "curated_skill"
    LEGACY_PROMPT = "legacy_prompt"


@dataclass(frozen=True)
class KnowledgeRecord:
    path: str
    kind: KnowledgeKind
    status: KnowledgeStatus
    authority: int
    sha256: str
    bytes: int
    flags: tuple[str, ...] = ()
    duplicate_of: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class GardenReport:
    scanned: int
    active: int
    review: int
    quarantined: int
    records: tuple[KnowledgeRecord, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "active": self.active,
            "review": self.review,
            "quarantined": self.quarantined,
            "records": [row.as_dict() for row in self.records],
        }


_CANONICAL_PATHS = {
    "docs/BLUEPRINT_V6.md": 110,
    "AGENTS.md": 100,
    "docs/EMPIRE_CODER.md": 98,
}

_CORE_ENGINEERING_SKILLS = frozenset({
    "empire_os/skills_library/skills/mcp-builder/SKILL.md",
    "empire_os/skills_library/skills/webapp-testing/SKILL.md",
})

_OBSOLETE_PATTERNS = (
    (re.compile(r"(?i)\bUSDC\s+(?:on|/|over)\s+Solana\b"), "obsolete_payment_rail"),
    (re.compile(r"(?i)\bSolana[- ]first\b"), "obsolete_payment_rail"),
    (re.compile(r"/root/empire_os/"), "stale_absolute_path"),
)

_OLD_BLUEPRINT_RE = re.compile(r"(?i)blueprint[_ -]?v([1-5])\b")


class KnowledgeGarden:
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
        self.promotions_root = (
            self.runtime_root
            / "knowledge"
            / "task_promotions"
        )
        self.promotions_root.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.promotions_root.chmod(0o700)

    def scan(self) -> GardenReport:
        candidates = list(self._candidates())
        seen_hash: dict[str, str] = {}
        records: list[KnowledgeRecord] = []

        for path, kind, authority in candidates:
            rel = str(path.relative_to(self.workspace))
            try:
                raw = path.read_bytes()
            except OSError:
                continue

            digest = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8", errors="replace")
            flags = list(self._flags(rel, text, kind))
            duplicate_of = seen_hash.get(digest)
            if duplicate_of:
                flags.append("exact_duplicate")
            else:
                seen_hash[digest] = rel

            status = self._status(
                rel=rel,
                kind=kind,
                authority=authority,
                flags=flags,
                duplicate_of=duplicate_of,
            )
            records.append(KnowledgeRecord(
                path=rel,
                kind=kind,
                status=status,
                authority=authority,
                sha256=digest,
                bytes=len(raw),
                flags=tuple(sorted(set(flags))),
                duplicate_of=duplicate_of,
            ))

        records.sort(key=lambda row: (-row.authority, row.path))
        return GardenReport(
            scanned=len(records),
            active=sum(r.status is KnowledgeStatus.ACTIVE for r in records),
            review=sum(r.status is KnowledgeStatus.REVIEW for r in records),
            quarantined=sum(
                r.status is KnowledgeStatus.QUARANTINED for r in records
            ),
            records=tuple(records),
        )

    def active_paths(
        self,
        report: GardenReport | None = None,
    ) -> tuple[str, ...]:
        report = report or self.scan()
        return tuple(
            row.path
            for row in report.records
            if row.status is KnowledgeStatus.ACTIVE
        )

    def promote_for_task(
        self,
        task_id: str,
        paths: Iterable[str],
        *,
        reason: str,
        approved: bool = False,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError(
                "task knowledge promotion requires explicit approval"
            )
        why = str(reason or "").strip()
        if not why:
            raise ValueError("promotion reason is required")

        report = self.scan()
        by_path = {row.path: row for row in report.records}
        entries = []
        for raw in dict.fromkeys(str(path) for path in paths):
            row = by_path.get(raw)
            if row is None:
                raise ValueError(
                    f"knowledge source not found: {raw}"
                )
            if row.status is KnowledgeStatus.QUARANTINED:
                raise PermissionError(
                    f"quarantined knowledge cannot be promoted: {raw}"
                )
            if row.status is KnowledgeStatus.ACTIVE:
                continue
            if row.status is not KnowledgeStatus.REVIEW:
                raise PermissionError(
                    f"knowledge source is not reviewable: {raw}"
                )
            entries.append({
                "path": row.path,
                "sha256": row.sha256,
                "status_at_promotion": row.status.value,
                "reason": why,
            })

        payload = {
            "version": 1,
            "task_id": self._safe_task_id(task_id),
            "approved_at": utc_now(),
            "entries": entries,
        }
        path = self._promotion_path(task_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.chmod(0o600)
        tmp.replace(path)
        path.chmod(0o600)
        return payload

    def active_paths_for_task(
        self,
        task_id: str,
        report: GardenReport | None = None,
    ) -> tuple[str, ...]:
        report = report or self.scan()
        active = list(self.active_paths(report))
        manifest = self._load_promotion(task_id)
        if not manifest:
            return tuple(active)

        by_path = {row.path: row for row in report.records}
        for entry in manifest.get("entries") or []:
            path = str(entry.get("path") or "")
            row = by_path.get(path)
            if row is None:
                continue
            if row.status is KnowledgeStatus.QUARANTINED:
                continue
            if row.sha256 != str(entry.get("sha256") or ""):
                continue
            if path not in active:
                active.append(path)
        return tuple(active)

    def task_promotion_status(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        manifest = self._load_promotion(task_id)
        if not manifest:
            return {
                "task_id": self._safe_task_id(task_id),
                "promoted": 0,
            }
        return {
            "task_id": manifest["task_id"],
            "promoted": len(manifest.get("entries") or []),
            "approved_at": manifest.get("approved_at"),
        }

    def _promotion_path(self, task_id: str) -> Path:
        safe = self._safe_task_id(task_id)
        return self.promotions_root / f"{safe}.json"

    def _load_promotion(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        path = self._promotion_path(task_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _safe_task_id(task_id: str) -> str:
        raw = str(task_id or "")
        safe = "".join(
            ch for ch in raw
            if ch.isalnum() or ch in "_-"
        )
        if not safe or safe != raw:
            raise ValueError("invalid task id")
        return safe

    def sync_manifest(
        self,
        destination: str | Path = "runtime/coder/knowledge/active.json",
        *,
        report: GardenReport | None = None,
    ) -> dict[str, Any]:
        report = report or self.scan()
        target = Path(destination)
        if not target.is_absolute():
            target = self.workspace / target
        target = target.resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError(
                "knowledge manifest must stay inside workspace"
            ) from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "policy": "active_only_default",
            "canonical_blueprint": "docs/BLUEPRINT_V6.md",
            "active": [
                row.as_dict()
                for row in report.records
                if row.status is KnowledgeStatus.ACTIVE
            ],
            "review": [
                row.as_dict()
                for row in report.records
                if row.status is KnowledgeStatus.REVIEW
            ],
            "quarantined": [
                row.as_dict()
                for row in report.records
                if row.status is KnowledgeStatus.QUARANTINED
            ],
        }
        tmp = target.with_name(
            f".{target.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(target)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        return payload

    def _candidates(
        self,
    ) -> Iterable[tuple[Path, KnowledgeKind, int]]:
        for rel, authority in _CANONICAL_PATHS.items():
            path = self.workspace / rel
            if path.is_file():
                yield path, KnowledgeKind.CANONICAL, authority

        legacy_artifacts = (
            self.workspace / "empire_os" / "blueprint_v5.md",
            self.workspace / "empire_os" / "data" / "prompts_index.json",
        )
        for path in legacy_artifacts:
            if path.is_file():
                yield path, KnowledgeKind.LEGACY_PROMPT, 10

        skills = (
            self.workspace
            / "empire_os"
            / "skills_library"
            / "skills"
        )
        if skills.is_dir():
            for path in sorted(skills.glob("*/SKILL.md")):
                yield path, KnowledgeKind.CURATED_SKILL, 80

        prompts = self.workspace / "empire_os" / "data" / "prompts"
        if prompts.is_dir():
            for path in sorted(prompts.iterdir()):
                if (
                    path.is_file()
                    and path.suffix.lower() in {".txt", ".md"}
                ):
                    yield path, KnowledgeKind.LEGACY_PROMPT, 30

    @staticmethod
    def _flags(
        rel: str,
        text: str,
        kind: KnowledgeKind,
    ) -> Iterable[str]:
        stripped = text.strip()
        if not stripped:
            yield "empty_content"
        if 0 < len(stripped) < 120:
            yield "very_thin_content"
        if (
            _OLD_BLUEPRINT_RE.search(text)
            and rel != "docs/BLUEPRINT_V6.md"
        ):
            yield "obsolete_blueprint_reference"
        if rel.endswith("blueprint_v5.md"):
            yield "obsolete_blueprint_reference"
        for pattern, flag in _OBSOLETE_PATTERNS:
            if pattern.search(text):
                yield flag
        if kind is KnowledgeKind.LEGACY_PROMPT:
            yield "legacy_prompt_source"

    @staticmethod
    def _status(
        *,
        rel: str,
        kind: KnowledgeKind,
        authority: int,
        flags: list[str],
        duplicate_of: str | None,
    ) -> KnowledgeStatus:
        flagset = set(flags)

        if kind is KnowledgeKind.CANONICAL:
            return KnowledgeStatus.ACTIVE

        if duplicate_of:
            return KnowledgeStatus.QUARANTINED

        hard_stale = {
            "obsolete_payment_rail",
            "stale_absolute_path",
            "obsolete_blueprint_reference",
            "empty_content",
        }
        if flagset & hard_stale:
            return KnowledgeStatus.QUARANTINED

        if kind is KnowledgeKind.CURATED_SKILL:
            return (
                KnowledgeStatus.ACTIVE
                if rel in _CORE_ENGINEERING_SKILLS
                else KnowledgeStatus.REVIEW
            )

        if kind is KnowledgeKind.LEGACY_PROMPT:
            return KnowledgeStatus.REVIEW

        return KnowledgeStatus.REVIEW
