"""Targeted context-pack construction and compaction."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .repo import RepoIntelligence
from .state import compact_task_context
from .models import CoderTask


@dataclass(frozen=True)
class ContextDocument:
    path: str
    reason: str
    excerpt: str


@dataclass(frozen=True)
class ContextPack:
    objective: str
    task_state: dict
    documents: tuple[ContextDocument, ...]
    symbols: tuple[dict, ...]
    token_budget_chars: int

    def as_dict(self) -> dict:
        return {
            "objective": self.objective,
            "task_state": self.task_state,
            "documents": [asdict(item) for item in self.documents],
            "symbols": list(self.symbols),
            "token_budget_chars": self.token_budget_chars,
        }


class ContextBuilder:
    def __init__(
        self,
        repo: RepoIntelligence,
        *,
        active_knowledge_paths: set[str] | None = None,
    ) -> None:
        self.repo = repo
        self.active_knowledge_paths = set(active_knowledge_paths or ())

    def set_active_knowledge_paths(
        self,
        paths: Iterable[str],
    ) -> None:
        self.active_knowledge_paths = set(str(path) for path in paths)

    def _knowledge_allowed(self, path: str) -> bool:
        guarded = (
            path.startswith("empire_os/data/prompts/")
            or path.startswith("empire_os/skills_library/")
        )
        if not guarded:
            return True
        return path in self.active_knowledge_paths

    def build(
        self,
        task: CoderTask,
        *,
        terms: Iterable[str] = (),
        symbol_terms: Iterable[str] = (),
        budget_chars: int = 24_000,
    ) -> ContextPack:
        documents: list[ContextDocument] = []
        seen_windows: set[tuple[str, int | None]] = set()
        seen_files: set[str] = set()
        remaining = max(int(budget_chars), 4_000)
        terms = tuple(
            dict.fromkeys(
                str(t).strip() for t in terms if str(t).strip()
            )
        )
        symbol_terms = tuple(
            dict.fromkeys(
                str(t).strip() for t in symbol_terms if str(t).strip()
            )
        )

        blueprint = task.blueprint_path
        blueprint_hits = []
        for term in terms or ("Empire Coder",):
            blueprint_hits.extend(
                hit for hit in self.repo.search(term, limit=10)
                if hit.path == blueprint
            )

        if blueprint_hits:
            hit = blueprint_hits[0]
            text = self.repo.excerpt(
                blueprint,
                line=hit.line,
                radius=14,
                max_chars=min(2_500, remaining),
            )
            if text:
                documents.append(ContextDocument(
                    blueprint,
                    f"architectural evidence near line {hit.line}",
                    text,
                ))
                remaining -= len(text)
                seen_windows.add((blueprint, hit.line))
                seen_files.add(blueprint)
        else:
            try:
                text = self.repo.excerpt(
                    blueprint,
                    radius=12,
                    max_chars=min(2_000, remaining),
                )
                if text:
                    documents.append(ContextDocument(
                        blueprint,
                        "architectural header evidence",
                        text,
                    ))
                    remaining -= len(text)
                    seen_files.add(blueprint)
            except (OSError, ValueError):
                pass

        symbols = []
        for term in symbol_terms:
            for hit in self.repo.symbols(term, limit=20):
                symbols.append({
                    "path": hit.path,
                    "line": hit.line,
                    "symbol": hit.text,
                })
                if remaining <= 0:
                    continue
                if hit.path in seen_files:
                    continue
                if not self._knowledge_allowed(hit.path):
                    continue
                try:
                    text = self.repo.excerpt(
                        hit.path,
                        line=hit.line,
                        radius=28,
                        max_chars=min(5_000, remaining),
                    )
                except (OSError, ValueError):
                    continue
                if not text:
                    continue
                documents.append(ContextDocument(
                    hit.path,
                    f"symbol definition evidence: {hit.text}",
                    text,
                ))
                remaining -= len(text)
                seen_windows.add((hit.path, hit.line))
                seen_files.add(hit.path)

        for term in terms:
            for hit in self.repo.search(term, limit=30):
                if remaining <= 0:
                    break
                if hit.path == blueprint:
                    continue
                if hit.path in seen_files:
                    continue
                if not self._knowledge_allowed(hit.path):
                    continue
                window = (hit.path, hit.line)
                if window in seen_windows:
                    continue
                try:
                    text = self.repo.excerpt(
                        hit.path,
                        line=hit.line,
                        radius=22,
                        max_chars=min(4_000, remaining),
                    )
                except (OSError, ValueError):
                    continue
                if not text:
                    continue
                documents.append(ContextDocument(
                    hit.path,
                    f"matched evidence near line {hit.line}: {term}",
                    text,
                ))
                remaining -= len(text)
                seen_windows.add(window)
                seen_files.add(hit.path)

        return ContextPack(
            objective=task.objective,
            task_state=compact_task_context(task),
            documents=tuple(documents),
            symbols=tuple(symbols),
            token_budget_chars=budget_chars,
        )
