"""Source-attested pre-change impact review for the existing Empire Coder.

Explicit owner-chosen Python files only. Evidence is limited to verified
Graphify AST links, not runtime impact, synthetic business data or code edits.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import json
from typing import Any, Iterable

from empire_os.graphify_code_snapshot import assert_snapshot_current
from empire_os.graphify_dual_bridge import import_graphify_code
from empire_os.graphify_code_impact import review_attested_code_impact
from .policy import resolve_path


class GraphifyChangeReviewer:
    def __init__(
        self, *, workspace: str | Path,
        graph_path: str | Path, snapshot_path: str | Path,
    ) -> None:
        self.workspace = Path(workspace).resolve(strict=True)
        self.graph_path = Path(graph_path)
        self.snapshot_path = Path(snapshot_path)

    @staticmethod
    def _bounded_json(path: Path) -> dict:
        if (path.is_symlink() or not path.is_file()
                or not 0 < path.stat().st_size <= 50_000_000):
            raise ValueError("unsafe Graphify graph evidence path")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Graphify evidence must be an object")
        return data

    def review(self, changed_paths: Iterable[str], *, max_affected: int = 20) -> dict[str, Any]:
        """Return observed incoming relationships, only after source attestation.

        Caller must already have permission to review this source repository.
        The paths themselves are verified with the current Coder path policy.
        """
        paths = tuple(changed_paths)
        if not paths or len(paths) > 15:
            raise ValueError("1-15 explicit changed files required")
        for path in paths:
            if not isinstance(path, str) or len(path) > 500:
                raise ValueError("invalid changed code path")
            parsed = PurePosixPath(path)
            if (parsed.is_absolute() or path != parsed.as_posix()
                    or not path.endswith(".py")
                    or any(part in ("", ".", "..") for part in parsed.parts)):
                raise ValueError("invalid changed code path")
            resolve_path(self.workspace, path)
        raw = self._bounded_json(self.graph_path)
        manifest = self._bounded_json(self.snapshot_path)
        assert_snapshot_current(
            manifest, source_root=self.workspace, graphify_export=raw,
        )
        result = review_attested_code_impact(
            import_graphify_code(raw), changed_paths=paths,
            max_affected=max_affected,
        )
        result.update({
            "source_graph_attested": True,
            "code_snapshot_sha256": manifest["snapshot_sha256"],
            "source_manifest_sha256": manifest["source_manifest"]["source_manifest_sha256"],
            "change_review_requires_human": True,
            "source_relationship_type": "EXTRACTED_STATIC_AST_ONLY",
            "patch_authorized": False,
            "customer_data_accessed": False,
        })
        return result
