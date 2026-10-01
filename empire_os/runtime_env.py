"""Safe runtime environment loader for production workers.

Exported environment variables win. Protected env files are fallback only.
This lets systemd inject secrets into non-root workers without those workers
needing permission to read the root-owned file themselves.

The canonical production runtime spans empire_os.env and empiredb.env. Loading
the former fills missing values from the latter; explicit custom files remain
isolated. Connection parsing and validation belong to the database connector.
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

    paths = [Path(path)]
    if paths[0] == Path("/etc/empire_os.env"):
        paths.append(Path("/etc/empiredb.env"))
    for p in paths:
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue

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
