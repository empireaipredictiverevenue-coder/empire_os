"""Dependency and test-target intelligence for Empire Coder."""
from __future__ import annotations

import ast
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .repo import RepoIntelligence


@dataclass(frozen=True)
class DependencyNode:
    path: str
    imports: tuple[str, ...]


class DependencyIndex:
    def __init__(self, repo: RepoIntelligence) -> None:
        self.repo = repo
        self.nodes: dict[str, DependencyNode] = {}
        self.reverse: dict[str, set[str]] = defaultdict(set)

    def build(self) -> "DependencyIndex":
        self.nodes.clear()
        self.reverse.clear()
        for rel in self.repo.tree(max_depth=8, limit=30_000):
            if not rel.endswith(".py"):
                continue
            try:
                imports = tuple(self.repo.python_imports(rel))
            except (OSError, SyntaxError, ValueError):
                continue
            self.nodes[rel] = DependencyNode(rel, imports)
        module_to_path = {
            self._module_name(path): path for path in self.nodes
        }
        for path, node in self.nodes.items():
            for imported in node.imports:
                target = self._resolve_import(imported, module_to_path)
                if target:
                    self.reverse[target].add(path)
        return self

    def dependents(
        self,
        path: str,
        *,
        depth: int = 2,
        limit: int = 100,
    ) -> list[str]:
        seen = {path}
        queue = deque([(path, 0)])
        out: list[str] = []
        while queue and len(out) < limit:
            current, level = queue.popleft()
            if level >= depth:
                continue
            for dep in sorted(self.reverse.get(current, ())):
                if dep in seen:
                    continue
                seen.add(dep)
                out.append(dep)
                queue.append((dep, level + 1))
                if len(out) >= limit:
                    break
        return out

    def impacted_tests(self, changed_files: Iterable[str]) -> list[str]:
        candidates: set[str] = set()
        for path in changed_files:
            candidates.update(self.repo.test_candidates(path))
            for dependent in self.dependents(path, depth=2):
                candidates.update(self.repo.test_candidates(dependent))
        return sorted(candidates)

    @staticmethod
    def _module_name(path: str) -> str:
        p = Path(path)
        parts = list(p.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)

    @staticmethod
    def _resolve_import(
        imported: str,
        module_to_path: dict[str, str],
    ) -> str | None:
        if imported in module_to_path:
            return module_to_path[imported]
        matches = [
            path for module, path in module_to_path.items()
            if module.endswith("." + imported) or imported.startswith(module + ".")
        ]
        return sorted(matches)[0] if matches else None
