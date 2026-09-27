"""Fail-closed audit for direct Supabase coupling in active EmpireOS runtime.

The canonical gateway may retain the legacy Supabase provider during the rollback
window, but business runtime modules must not read Supabase credentials, build
Supabase URLs, or call PostgREST directly.

Explicitly classified exceptions are migration/recovery/observer boundaries, not
canonical business-runtime dependencies.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOTS = ("empire_os", "scripts")

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("supabase_url_env", re.compile(r"\bSUPABASE_URL\b")),
    ("supabase_service_key_env", re.compile(r"\bSUPABASE_SERVICE_KEY\b")),
    ("supabase_key_symbol", re.compile(r"\bSUPABASE_KEY\b")),
    ("supabase_host", re.compile(r"\.supabase\.co\b", re.I)),
    ("postgrest_path", re.compile(r"/rest/v1/")),
    (
        "direct_sb_import",
        re.compile(
            r"(?:from\s+empire_os\s+import\s+sb\b|"
            r"import\s+empire_os\.sb\b)"
        ),
    ),
    ("direct_sb_vendor_attr", re.compile(r"\bsb\.SUPABASE_[A-Z_]+\b")),
)

# These files are intentionally outside the canonical business-runtime path.
# Keeping them here is explicit classification, not silent exclusion.
CLASSIFIED_EXCEPTIONS = {
    "empire_os/sb.py": "legacy_compatibility_facade",
    "empire_os/data_backends/supabase_legacy.py": "legacy_provider_adapter",
    "empire_os/activate_idle_leads.py": "one_time_migration_recovery",
    "empire_os/astra_preflight.py": "explicit_legacy_astra_observer",
    "scripts/astra_observer.py": "explicit_legacy_astra_observer",
}

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "tests",
    "docs",
    "migrations",
    "recovery",
    "toop",
    "runtime",
}


def iter_files(repo_root: Path):
    for root_name in ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            yield path


def audit(repo_root: Path) -> dict[str, object]:
    active_hits: list[dict[str, object]] = []
    classified_hits: list[dict[str, object]] = []

    for path in iter_files(repo_root):
        relative = str(path.relative_to(repo_root))
        try:
            lines = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except OSError:
            continue

        classification = CLASSIFIED_EXCEPTIONS.get(relative)
        for line_number, line in enumerate(lines, start=1):
            for kind, pattern in PATTERNS:
                if not pattern.search(line):
                    continue
                item = {
                    "file": relative,
                    "line": line_number,
                    "kind": kind,
                    "excerpt": line.strip()[:220],
                }
                if classification:
                    classified_hits.append({
                        **item,
                        "classification": classification,
                    })
                else:
                    active_hits.append(item)

    return {
        "schema_version": "empire.vendor-coupling-audit.v1",
        "read_only": True,
        "production_cutover_authority": False,
        "active_direct_vendor_hits": active_hits,
        "active_direct_vendor_count": len(active_hits),
        "classified_exception_hits": classified_hits,
        "classified_exception_count": len(classified_hits),
        "classified_exception_files": CLASSIFIED_EXCEPTIONS,
        "verified": len(active_hits) == 0,
    }


def main() -> int:
    report = audit(Path.cwd())
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
