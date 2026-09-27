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
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_URL",
    "canonical_supabase",
    "supabase.co",
    "supabase",
)


@dataclass(frozen=True)
class DependencyFinding:
    path: str
    marker: str
    line_number: int
    classification: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _eligible(path: Path) -> bool:
    return path.is_file() and path.suffix in TEXT_SUFFIXES and not any(
        part in SKIP_PARTS for part in path.parts
    )


APPROVED_VENDOR_BOUNDARIES = {
    "empire_os/canonical_data_gateway.py": "canonical_gateway",
    "empire_os/data_backends/supabase_legacy.py": "legacy_adapter",
    "empire_os/data_backends/astra_token_legacy.py": "legacy_adapter",
    "empire_os/supabase_egress_guard.py": "migration_containment",
    "empire_os/legacy_data_containment.py": "migration_containment",
    "scripts/run_supabase_egress_guard.py": "migration_containment",
}


def _classification_for_path(relative: str) -> str:
    if relative in APPROVED_VENDOR_BOUNDARIES:
        return APPROVED_VENDOR_BOUNDARIES[relative]
    if relative.startswith("tests/"):
        return "test_reference"
    if relative.startswith("docs/"):
        return "documentation"
    if relative in {
        "empire_os/data_cloud_discovery.py",
        "empire_os/data_cloud_readiness.py",
    }:
        return "migration_tooling"
    if relative.endswith((".env.example", ".env.sample")):
        return "configuration_template"
    if relative.startswith(("deploy/", "scripts/")):
        return "runtime_integration"
    if relative.startswith("apps/"):
        return "application_runtime"
    if relative.startswith("empire_os/"):
        return "production_runtime"
    return "requires_review"


def _first_marker(line: str, markers: tuple[str, ...]) -> str | None:
    lowered = line.lower()
    for marker in sorted(markers, key=len, reverse=True):
        if marker.lower() in lowered:
            return marker
    return None


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
        classification = _classification_for_path(relative)
        for line_number, line in enumerate(text.splitlines(), start=1):
            marker = _first_marker(line, marker_tuple)
            if marker is None:
                continue
            findings.append(
                DependencyFinding(
                    path=relative,
                    marker=marker,
                    line_number=line_number,
                    classification=classification,
                )
            )
    return tuple(findings)
