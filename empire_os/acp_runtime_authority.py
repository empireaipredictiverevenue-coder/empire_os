"""Root-bound runtime capability for EmpireOS ACP."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from empire_os.predictive_cloud_fabric import ExecutionAuthority


DEFAULT_ACP_CAPABILITY_PATH = Path(
    "/etc/empire_acp_internal_authority"
)


def load_acp_execution_authority(
    path: str | Path = DEFAULT_ACP_CAPABILITY_PATH,
) -> tuple[ExecutionAuthority | None, str]:

    target = os.fspath(path)

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )

    try:
        fd = os.open(target, flags)
    except FileNotFoundError:
        return None, "capability_absent"
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return None, "capability_symlink_rejected"
        return None, "capability_unreadable"

    try:
        meta = os.fstat(fd)

        if not stat.S_ISREG(meta.st_mode):
            return None, "capability_not_regular_file"

        if meta.st_uid != 0:
            return None, "capability_owner_rejected"

        if stat.S_IMODE(meta.st_mode) & 0o077:
            return None, "capability_permissions_rejected"

        raw = os.read(fd, 128)

        # Capability files must remain tiny.
        if os.read(fd, 1):
            return None, "capability_value_rejected"

    finally:
        os.close(fd)

    try:
        value = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None, "capability_value_rejected"

    if value != ExecutionAuthority.EXECUTE_BOUNDED.value:
        return None, "capability_value_rejected"

    return (
        ExecutionAuthority.EXECUTE_BOUNDED,
        "root_capability_file",
    )
