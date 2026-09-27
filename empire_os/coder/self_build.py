"""Controlled self-improvement guard for Empire Coder."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable


_DEFAULT_SELF_BUILD_PREFIXES = (
    "empire_os/coder/",
    "tests/coder/",
    "docs/EMPIRE_CODER",
    "scripts/empire_coder",
    "config/empire_coder",
)


class SelfBuildScopeError(RuntimeError):
    pass


def validate_self_build_scope(
    changed_files: Iterable[str],
    *,
    allowed_prefixes: tuple[str, ...] = _DEFAULT_SELF_BUILD_PREFIXES,
) -> tuple[str, ...]:
    normalized: list[str] = []
    violations: list[str] = []
    for raw in changed_files:
        path = str(PurePosixPath(str(raw)))
        normalized.append(path)
        if not any(path.startswith(prefix) for prefix in allowed_prefixes):
            violations.append(path)
    if violations:
        raise SelfBuildScopeError(
            "self-build attempted changes outside Empire Coder scope: "
            + ", ".join(sorted(violations))
        )
    return tuple(normalized)
