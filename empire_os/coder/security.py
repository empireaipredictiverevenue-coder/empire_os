"""Security scanning for Empire Coder patches and tool output."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .policy import PROTECTED_NAMES, resolve_workspace


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    # Require an actual literal secret value. Generic variables such as
    # ``token = os.getenv(...)`` or public token-contract constants are not
    # secret material and must not fail deterministic verification.
    re.compile(
        r"(?i)(api[_-]?key|secret|password|(?:access|auth|bearer|service)[_-]?token)"
        r"\s*[:=]\s*['\"][^'\"\r\n]{12,}['\"]"
    ),
    re.compile(
        r"(?im)^\s*(?:[A-Z0-9_]*(?:SECRET|PASSWORD|API[_-]?KEY|ACCESS[_-]?TOKEN))"
        r"\s*=\s*[A-Za-z0-9_./+=:-]{16,}\s*$"
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)mnemonic\s*[:=]"),
)
_DANGEROUS_DIFF = (
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\bsubprocess\.(?:Popen|call|run)\([^\n]*shell\s*=\s*True"),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\brm\s+-rf\b"),
)


@dataclass(frozen=True)
class SecurityFinding:
    kind: str
    severity: str
    message: str
    path: str | None = None


def scrub_text(text: str) -> str:
    clean = str(text or "")
    for pattern in _SECRET_PATTERNS:
        clean = pattern.sub("[REDACTED]", clean)
    return clean


def scan_text(text: str, *, path: str | None = None) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(SecurityFinding(
                "secret_material", "critical",
                "secret-like material detected", path,
            ))
            break
    for pattern in _DANGEROUS_DIFF:
        match = pattern.search(text)
        if match:
            findings.append(SecurityFinding(
                "dangerous_code", "high",
                f"dangerous pattern detected: {match.group(0)[:80]}",
                path,
            ))
    return findings


def scan_paths(
    workspace: str | Path,
    paths: Iterable[str],
) -> list[SecurityFinding]:
    root = resolve_workspace(workspace)
    findings: list[SecurityFinding] = []
    for raw in paths:
        path = Path(raw)
        if any(part in PROTECTED_NAMES for part in path.parts):
            findings.append(SecurityFinding(
                "protected_path", "critical",
                "protected path present in candidate change", str(path),
            ))
            continue
        target = root / path
        if not target.is_file():
            continue
        try:
            data = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_text(data, path=str(path)))
    return findings
