"""Safe runtime environment loader for production workers.

Exported environment variables win. Protected env files are fallback only.
This lets systemd inject secrets into non-root workers without those workers
needing permission to read the root-owned file themselves.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def load_runtime_env(
    path: str | Path,
    *,
    required: Iterable[str] = (),
) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if value not in (None, "")
    }

    p = Path(path)
    try:
        content = p.read_text(encoding="utf-8")
    except (OSError, PermissionError):
        content = ""

    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value and key not in env:
            env[key] = value

    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(
            "missing required runtime env: " + ",".join(sorted(missing))
        )

    return env
