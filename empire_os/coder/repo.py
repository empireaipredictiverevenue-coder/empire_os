"""Targeted repository intelligence for Empire Coder."""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Iterable

from .models import RepoHit
from .policy import PROTECTED_NAMES, is_sensitive_path, resolve_path, resolve_workspace


_SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "recovery", "toop", "tools",
})


class RepoIntelligence:
    def __init__(self, workspace: str | Path) -> None:
        self.root = resolve_workspace(workspace)

    def tree(self, *, max_depth: int = 3, limit: int = 500) -> list[str]:
        results: list[str] = []
        for current, dirs, files in os.walk(self.root):
            rel_dir = Path(current).relative_to(self.root)
            if len(rel_dir.parts) >= max_depth:
                dirs[:] = []
            else:
                dirs[:] = sorted(
                    name for name in dirs
                    if name not in _SKIP_DIRS
                )
            for name in sorted(files):
                rel = rel_dir / name
                if any(part in PROTECTED_NAMES for part in rel.parts):
                    continue
                if is_sensitive_path(rel):
                    continue
                results.append(str(rel))
                if len(results) >= limit:
                    return results
        return results

    def read(self, path: str, *, max_chars: int = 60_000) -> str:
        target = resolve_path(self.root, path)
        data = target.read_text(encoding="utf-8", errors="replace")
        return data[:max_chars]

    def search(
        self,
        query: str,
        *,
        suffixes: Iterable[str] | None = None,
        limit: int = 100,
    ) -> list[RepoHit]:
        needle = str(query or "").strip()
        if not needle:
            return []
        allowed = set(suffixes or ())
        hits: list[RepoHit] = []
        for rel in self.tree(max_depth=8, limit=20_000):
            path = self.root / rel
            if not path.is_file():
                continue
            if allowed and path.suffix not in allowed:
                continue
            try:
                lines = path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, 1):
                if needle.lower() in line.lower():
                    hits.append(RepoHit(rel, number, line[:500]))
                    if len(hits) >= limit:
                        return hits
        return hits

    def symbols(self, name: str, *, limit: int = 50) -> list[RepoHit]:
        target = str(name or "").strip().lower()
        if not target:
            return []
        hits: list[RepoHit] = []
        for rel in self.tree(max_depth=8, limit=20_000):
            path = self.root / rel
            if path.suffix != ".py":
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ) and target in node.name.lower():
                    hits.append(
                        RepoHit(rel, node.lineno, node.name, "symbol")
                    )
                    if len(hits) >= limit:
                        return hits
        return hits



    def excerpt(
        self,
        path: str,
        *,
        line: int | None = None,
        radius: int = 20,
        max_chars: int = 8_000,
    ) -> str:
        target = resolve_path(self.root, path)
        lines = target.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        if not lines:
            return ""
        if line is None:
            selected = lines[: max(radius * 2 + 1, 1)]
        else:
            index = max(int(line) - 1, 0)
            start = max(index - max(radius, 0), 0)
            end = min(index + max(radius, 0) + 1, len(lines))
            selected = lines[start:end]
        return "\n".join(selected)[:max_chars]

    def python_imports(self, path: str) -> list[str]:
        source = self.read(path)
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return sorted(set(imports))

    def test_candidates(self, path: str) -> list[str]:
        stem = Path(path).stem.lower()
        candidates: list[str] = []
        for rel in self.tree(max_depth=8, limit=20_000):
            if not rel.startswith("tests/"):
                continue
            name = Path(rel).name.lower()
            if stem in name or name == f"test_{stem}.py":
                candidates.append(rel)
        return candidates[:50]

    def blueprint(self, path: str = "docs/BLUEPRINT_V6.md") -> str:
        return self.read(path, max_chars=120_000)
