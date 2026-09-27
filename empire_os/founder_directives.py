"""Durable Founder Directive intake for EmpireOS.

Every founder idea becomes business state instead of chat-only context:
capture -> dedupe -> classify -> plan -> implementation-ready/founder-gate.
This module never deploys, sends outbound, accepts terms, moves funds, or
recognizes revenue.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

VALID_STATUSES = {
    "captured",
    "planning",
    "planned",
    "implementation_ready",
    "implementing",
    "implementation_failed",
    "verification_required",
    "verifying",
    "verification_failed",
    "founder_gate",
    "plan_failed",
    "implemented",
    "rejected",
}

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("revenue", ("revenue", "buyer", "sales", "outbound", "lead", "gtm", "closer", "crm")),
    ("search", ("seo", "serp", "aeo", "geo", "search", "backlink", "mention")),
    ("intelligence", ("forecast", "timesfm", "omega", "cortex", "intent", "market", "signal")),
    ("security", ("security", "rls", "authentik", "kubescape", "auth", "mfa", "rbac")),
    ("product", ("product", "pricing", "saas", "white label", "dashboard", "app")),
    ("infrastructure", ("server", "kubernetes", "docker", "systemd", "cloudflare", "mcp", "database")),
    ("research", ("research", "youtube", "repo", "competitor", "strategy")),
    ("design", ("website", "page", "design", "3d", "animation", "premium")),
)

FOUNDER_GATE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(move|send|transfer|withdraw|pay)\b.{0,40}\b(funds?|money|usdt|crypto)\b", "fund_movement"),
    (r"\b(mainnet|production chain|irreversible accounting)\b", "irreversible_financial_system"),
    (r"\b(accept|sign|agree)\b.{0,40}\b(contract|terms|agreement)\b", "binding_commercial_terms"),
    (r"\b(recognize|recognise|book)\b.{0,30}\brevenue\b", "revenue_recognition"),
    (r"\b(drop|truncate|destroy|wipe|delete all)\b.{0,40}\b(table|database|infra|production)\b", "destructive_infrastructure"),
    (r"\b(expand|widen|grant)\b.{0,40}\b(authority|permission|admin|root|production)\b", "authority_expansion"),
)

NORMALIZE = re.compile(r"[^a-z0-9]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_directive_text(text: str) -> str:
    return " ".join(NORMALIZE.sub(" ", str(text or "").lower()).split())


def directive_fingerprint(text: str) -> str:
    normalized = normalize_directive_text(text)
    if not normalized:
        raise ValueError("directive text required")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def classify_category(text: str) -> str:
    normalized = normalize_directive_text(text)
    scores: list[tuple[int, int, str]] = []
    for index, (category, terms) in enumerate(CATEGORY_RULES):
        score = sum(term in normalized for term in terms)
        if score:
            scores.append((score, -index, category))
    return max(scores)[2] if scores else "general"


def classify_authority(text: str) -> tuple[str, tuple[str, ...]]:
    normalized = normalize_directive_text(text)
    gates = tuple(
        label for pattern, label in FOUNDER_GATE_PATTERNS
        if re.search(pattern, normalized, re.I)
    )
    if gates:
        return "founder_gate", gates
    return "internal_plan", ()


@dataclass
class FounderDirective:
    id: str
    fingerprint: str
    text: str
    title: str
    source: str
    category: str
    priority: int
    authority: str
    gate_reasons: tuple[str, ...] = ()
    status: str = "captured"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    coder_task_id: str | None = None
    coder_job_id: str | None = None
    plan_result: dict[str, Any] = field(default_factory=dict)
    implementation_task_id: str | None = None
    implementation_job_id: str | None = None
    implementation_result: dict[str, Any] = field(default_factory=dict)
    verification_task_id: str | None = None
    verification_job_id: str | None = None
    verification_result: dict[str, Any] = field(default_factory=dict)
    commit_sha: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gate_reasons"] = list(self.gate_reasons)
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FounderDirective":
        payload = dict(raw)
        payload["gate_reasons"] = tuple(payload.get("gate_reasons") or ())
        return cls(**payload)


class FounderDirectiveStore:
    def __init__(
        self,
        repo_root: str | Path,
        *,
        runtime_root: str | Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.runtime_root = Path(
            runtime_root
            or self.repo_root / "runtime" / "founder_directives"
        ).resolve()
        self.records = self.runtime_root / "records"
        self.records.mkdir(parents=True, exist_ok=True)
        os.chmod(self.runtime_root, 0o700)
        os.chmod(self.records, 0o700)
        self.lock_path = self.runtime_root / ".directives.lock"
        self.lock_path.touch(exist_ok=True)
        os.chmod(self.lock_path, 0o600)

    @contextmanager
    def _locked(self):
        with self.lock_path.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def ingest(
        self,
        text: str,
        *,
        source: str = "founder",
        title: str | None = None,
        priority: int = 90,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[FounderDirective, bool]:
        clean = " ".join(str(text or "").split()).strip()
        if not clean:
            raise ValueError("directive text required")
        if len(clean) > 20000:
            raise ValueError("directive text too long")
        fingerprint = directive_fingerprint(clean)
        with self._locked():
            existing = self.find_by_fingerprint(fingerprint)
            if existing is not None:
                return existing, False
            authority, gates = classify_authority(clean)
            directive = FounderDirective(
                id=f"directive_{uuid4().hex}",
                fingerprint=fingerprint,
                text=clean,
                title=(
                    str(title or "").strip()
                    or clean[:120]
                ),
                source=str(source or "founder").strip() or "founder",
                category=classify_category(clean),
                priority=max(0, min(int(priority), 100)),
                authority=authority,
                gate_reasons=gates,
                metadata=dict(metadata or {}),
            )
            self._write(directive)
            self.write_snapshot()
            return directive, True

    def get(self, directive_id: str) -> FounderDirective:
        safe = self._safe_id(directive_id)
        path = self.records / f"{safe}.json"
        if not path.exists():
            raise KeyError(safe)
        return FounderDirective.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def update(
        self,
        directive_id: str,
        **changes: Any,
    ) -> FounderDirective:
        with self._locked():
            directive = self.get(directive_id)
            data = directive.as_dict()
            for key, value in changes.items():
                if key not in data:
                    raise ValueError(f"unsupported directive field: {key}")
                data[key] = value
            data["updated_at"] = utc_now()
            if data.get("status") not in VALID_STATUSES:
                raise ValueError("invalid directive status")
            updated = FounderDirective.from_dict(data)
            self._write(updated)
            self.write_snapshot()
            return updated

    def list(
        self,
        *,
        statuses: Iterable[str] | None = None,
    ) -> list[FounderDirective]:
        allowed = set(statuses or ())
        output: list[FounderDirective] = []
        for path in sorted(self.records.glob("directive_*.json")):
            try:
                row = FounderDirective.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            if allowed and row.status not in allowed:
                continue
            output.append(row)
        output.sort(key=lambda row: (-row.priority, row.created_at, row.id))
        return output

    def find_by_fingerprint(
        self,
        fingerprint: str,
    ) -> FounderDirective | None:
        for row in self.list():
            if row.fingerprint == fingerprint:
                return row
        return None

    def summary(self) -> dict[str, Any]:
        rows = self.list()
        statuses: dict[str, int] = {}
        categories: dict[str, int] = {}
        for row in rows:
            statuses[row.status] = statuses.get(row.status, 0) + 1
            categories[row.category] = categories.get(row.category, 0) + 1
        gates = [row for row in rows if row.authority == "founder_gate"]
        return {
            "schema_version": "empire.founder_directives.v1",
            "observed_at": utc_now(),
            "directive_count": len(rows),
            "status_counts": dict(sorted(statuses.items())),
            "category_counts": dict(sorted(categories.items())),
            "founder_gate_count": len(gates),
            "automatic_planning": True,
            "automatic_production_execution": False,
            "execution_mode": "OBSERVE",
            "latest": [
                {
                    "id": row.id,
                    "title": row.title,
                    "category": row.category,
                    "status": row.status,
                    "authority": row.authority,
                    "priority": row.priority,
                    "coder_task_id": row.coder_task_id,
                    "coder_job_id": row.coder_job_id,
                    "implementation_task_id": row.implementation_task_id,
                    "implementation_job_id": row.implementation_job_id,
                    "verification_task_id": row.verification_task_id,
                    "verification_job_id": row.verification_job_id,
                    "commit_sha": row.commit_sha,
                }
                for row in sorted(
                    rows,
                    key=lambda item: item.updated_at,
                    reverse=True,
                )[:20]
            ],
        }

    def write_snapshot(self) -> Path:
        target = self.runtime_root / "latest.json"
        self._atomic_json(target, self.summary())
        return target

    def _write(self, directive: FounderDirective) -> None:
        self._atomic_json(
            self.records / f"{self._safe_id(directive.id)}.json",
            directive.as_dict(),
        )

    @staticmethod
    def _safe_id(value: str) -> str:
        raw = str(value or "")
        if not raw.startswith("directive_"):
            raise ValueError("invalid directive id")
        if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in raw):
            raise ValueError("invalid directive id")
        return raw

    @staticmethod
    def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
        tmp = path.with_name(
            f".{path.name}.{uuid4().hex}.tmp"
        )
        try:
            tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.chmod(tmp, 0o600)
            tmp.replace(path)
            os.chmod(path, 0o600)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
