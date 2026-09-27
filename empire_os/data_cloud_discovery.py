"""Read-only discovery for vendor-specific data dependencies."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".toml",
    ".yaml", ".yml", ".service", ".timer", ".sh",
}
SKIP_PARTS = {
    ".git", ".venv", "node_modules", "runtime", "recovery", "toop",
}
VENDOR_MARKERS = (
    "supabase",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "canonical_supabase",
)


@dataclass(frozen=True)
class DependencyFinding:
    path: str
    marker: str
    line_number: int
    classification: str = "requires_review"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _eligible(path: Path) -> bool:
    return path.is_file() and path.suffix in TEXT_SUFFIXES and not any(
        part in SKIP_PARTS for part in path.parts
    )


def discover_vendor_dependencies(
    repo_root: str | Path,
    *,
    markers: Iterable[str] = VENDOR_MARKERS,
) -> tuple[DependencyFinding, ...]:
    """Scan repository text without network or data mutations."""

    root = Path(repo_root).resolve()
    marker_tuple = tuple(str(marker) for marker in markers if str(marker))
    findings: list[DependencyFinding] = []

    for path in sorted(root.rglob("*")):
        if not _eligible(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for marker in marker_tuple:
                if marker in line:
                    findings.append(
                        DependencyFinding(
                            path=relative,
                            marker=marker,
                            line_number=line_number,
                        )
                    )
    return tuple(findings)
