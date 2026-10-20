"""Opt-in, source-attested Graphify context for the existing Empire Coder.

Graphify node labels are untrusted hints. This provider only returns actual
source excerpts via RepoIntelligence's existing path/secret policy. No live
Graphify extraction or hosted model runs during context building.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Iterable

from empire_os.graphify_code_snapshot import assert_snapshot_current
from empire_os.graphify_dual_bridge import import_graphify_code
from .graphify_relevance import rank_attested_code_paths

from .context import ContextDocument
from .repo import RepoIntelligence


_LINE = re.compile(r"^L([1-9][0-9]{0,7})$")


class GraphifyContextSource:
    """Optional, fail-closed code-only context provider, owned by Graphify."""

    def __init__(
        self, *, workspace: str | Path, graph_path: str | Path,
        snapshot_path: str | Path,
    ) -> None:
        self.workspace = Path(workspace).resolve(strict=True)
        self.graph_path = Path(graph_path)
        self.snapshot_path = Path(snapshot_path)

    @staticmethod
    def _read(path: Path, *, max_bytes: int) -> dict:
        if (path.is_symlink() or not path.is_file() or
                not 0 < path.stat().st_size <= max_bytes):
            raise ValueError("Graphify code context input missing or unsafe")
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Graphify code context must be an object")
        return result

    def documents(
        self, *, terms: Iterable[str], repo: RepoIntelligence,
        max_docs: int = 3, max_chars: int = 2200,
    ) -> tuple[ContextDocument, ...]:
        if (repo.root != self.workspace or type(max_docs) is not int or
                type(max_chars) is not int or not 1 <= max_docs <= 5 or
                not 1 <= max_chars <= 6000):
            raise ValueError("Graphify context policy mismatch")
        raw = self._read(self.graph_path, max_bytes=50_000_000)
        snap = self._read(self.snapshot_path, max_bytes=50_000_000)
        assert_snapshot_current(
            snap, source_root=self.workspace, graphify_export=raw,
        )
        imported = import_graphify_code(raw)
        # Only explicit caller terms; never invent a "semantic match" using
        # external embeddings or cross-tenant commercial evidence.
        query_terms = tuple(
            dict.fromkeys(
                value.strip() for value in terms
                if isinstance(value, str) and 2 <= len(value.strip()) <= 128
            )
        )[:8]
        ranked = rank_attested_code_paths(
            imported, terms=query_terms, max_files=max_docs,
        )
        documents = []
        left = max_chars
        for item in ranked:
            src, location = item["source_file"], item["source_location"]
            if left < 100:
                break
            # Source allowlist attestation has already verified source_file
            # presence, and RepoIntelligence enforces protected/secret paths.
            match = _LINE.fullmatch(location)
            line = int(match.group(1)) if match else None
            text = repo.excerpt(
                src, line=line, radius=8, max_chars=min(1000, left),
            )
            if not text:
                continue
            documents.append(ContextDocument(
                path=src,
                reason=(
                    "attested Graphify code relationship; source excerpt; "
                    + item["reason"].lower()
                ),
                excerpt=text,
            ))
            left -= len(text)
        return tuple(documents)
