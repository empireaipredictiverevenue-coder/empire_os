"""
Shared guard-rails for Empire OS autonomous agents.

Both the Code Review Agent and North-mini Agent load this so they can run
free-tier LLMs WITHOUT doing anything dangerous. Enforcement is defensive:
even if the LLM "asks" for a forbidden action, it is blocked + logged.

Modes:
  "read_only"  -> Code Review: may NOT write/exec/move/delete any code or
                  system file. Only appends verdicts to its findings.jsonl.
  "artifact"   -> North-mini: may ONLY write planning artifacts to
                  /root/feedback + /root/g-brain. No live system mutation,
                  no charging, no external POSTs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Secrets we never let an LLM echo back into stored output / findings.
_SECRET_RE = re.compile(
    r"(sk-or-[A-Za-z0-9_-]{20,}|sk-pUr[0-9A-Za-z]{20,}|"
    r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"Bearer\s+[A-Za-z0-9._-]{20,}|"
    r"api[_-]?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9]{16,})",
    re.IGNORECASE,
)

# Forbidden action patterns an LLM might try to embed in "fix" text.
_FORBIDDEN = [
    r"\brm\s+-rf\b", r"\bgit\s+push\b", r"\bgit\s+reset\s+--hard\b",
    r"\bdelete\s+from\b", r"\bdrop\s+table\b", r"\bshutdown\b",
    r"\bpm2\s+(delete|kill)\b", r"\bcurl\b.*\b(exec|eval)\b",
    r"\bos\.system\b", r"\beval\s*\(", r"\bexec\s*\(",
    r"\b__import__\b", r"\bsubprocess\b",
]

_FORBIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in _FORBIDDEN]


def scrub_secrets(text: str) -> str:
    """Remove any secret-looking strings from LLM output before persisting."""
    if not text:
        return text
    return _SECRET_RE.sub("[REDACTED]", text)


def has_forbidden(text: str) -> list[str]:
    """Return list of forbidden patterns found in text (empty = clean)."""
    if not text:
        return []
    hits = []
    for rx in _FORBIDDEN_RE:
        m = rx.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def enforce_mode(text: str, mode: str, role: str) -> tuple[str, list[str]]:
    """Scrub secrets + flag forbidden actions. Returns (clean_text, violations)."""
    clean = scrub_secrets(text)
    violations = has_forbidden(clean)
    if violations:
        import logging
        logging.getLogger(role).warning(
            "GUARDRAIL[%s] blocked forbidden action(s): %s", mode, violations)
    return clean, violations


def safe_write(path: Path, content: str, mode: str, role: str) -> bool:
    """Write only if path is allowed for the agent's mode. Returns success."""
    path = Path(path).resolve()
    allowed = []
    if mode == "read_only":
        allowed = [Path("/root/code_review").resolve()]
    elif mode == "artifact":
        allowed = [Path("/root/feedback").resolve(),
                   Path("/root/g-brain").resolve()]
    if not any(str(path).startswith(str(a)) for a in allowed):
        import logging
        logging.getLogger(role).warning(
            "GUARDRAIL[%s] write BLOCKED outside scope: %s", mode, path)
        return False
    clean, violations = enforce_mode(content, mode, role)
    if violations:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if path.exists() else "w") as f:
        f.write(clean if isinstance(clean, str) else json.dumps(clean))
    return True
