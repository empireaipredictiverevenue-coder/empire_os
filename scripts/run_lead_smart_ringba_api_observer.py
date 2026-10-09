#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from empire_os.lead_smart_ringba_api_observer import (
    observe_from_environment,
)


OUT = Path(
    "runtime/revenue/lead_smart/"
    "ringba/api_observation/latest.json"
)


def write_observation(result: dict[str, Any], *, out: Path = OUT) -> None:
    """
    Atomically persist SANITIZED affiliate call evidence for the EmpireOS reader.

    API observation is sometimes executed as root to load protected Ringba
    credentials. Root ownership must not hide its redacted output from the
    unprivileged EmpireOS reader. Owner/group follow the existing Ringba
    runtime directory, never a caller-supplied username or environment var.
    """
    ringba_root = out.parent.parent
    owner = ringba_root.lstat()
    if not stat.S_ISDIR(owner.st_mode):
        raise RuntimeError("Ringba evidence root must be a real directory")

    if os.geteuid() == 0 and owner.st_uid == 0:
        raise RuntimeError("non-root Ringba evidence reader owner required")

    out.parent.mkdir(parents=True, exist_ok=True)

    # Each run gets its own temporary path; no partial latest.json is exposed.
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=out.parent,
            prefix=".latest.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(temp_path, 0o640)
        if os.geteuid() == 0:
            os.chown(temp_path, owner.st_uid, owner.st_gid)
            os.chown(out.parent, owner.st_uid, owner.st_gid)
            os.chmod(out.parent, 0o750)

        os.replace(temp_path, out)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    result = observe_from_environment()
    write_observation(result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
