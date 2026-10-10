"""Isolated TAM research reader credential only; no Market GPS fallback.

Not provisioned/activated by importing this module. Systemd LoadCredential
places a short-lived read-only file in the specific on-demand unit.
"""
from __future__ import annotations

import os
from pathlib import Path


CREDENTIAL_NAME = "tam-market.dsn"
UNIT_CREDENTIAL_DIR = Path(
    "/run/credentials/empire-tam-market-read.service"
)


def load_tam_isolated_dsn(
    credential_directory: str | Path | None = None,
) -> str:
    """Load only a private, specific TAM identity; never discover other secrets."""
    raw = credential_directory
    if raw is None:
        raw = os.environ.get("CREDENTIALS_DIRECTORY")
        if raw != str(UNIT_CREDENTIAL_DIR):
            raise ValueError("isolated TAM systemd credential context required")
    if not raw:
        raise ValueError("isolated TAM credential directory required")
    directory = Path(raw)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("invalid isolated TAM credential directory")
    path = directory / CREDENTIAL_NAME
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or unsafe isolated TAM credential")
    file_mode = path.stat().st_mode & 0o777
    dir_mode = directory.stat().st_mode & 0o777
    delivered_by_systemd = (
        raw == str(UNIT_CREDENTIAL_DIR)
        and os.environ.get("CREDENTIALS_DIRECTORY") == str(UNIT_CREDENTIAL_DIR)
    )
    # systemd may expose the delivered read-only copy as 0444 inside its
    # private per-unit credential directory. Never demand the root SOURCE
    # file's 0400 mode from this copy; never accept another directory.
    if delivered_by_systemd:
        unsafe_mode = (
            bool(file_mode & 0o222)  # no writes by anyone
            or bool(dir_mode & 0o007)  # no traverse by unrelated users
        )
    else:
        # Explicit/test credentials outside the real systemd unit context
        # must retain strict owner-only mode.
        unsafe_mode = bool(file_mode & 0o077)
    if unsafe_mode or not 10 <= path.stat().st_size <= 2048:
        raise ValueError("missing or unsafe isolated TAM credential")
    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise ValueError("isolated TAM credential unreadable") from None
    # Validate without retaining, logging or returning any other capability.
    from empire_os.tam_market_runtime import _validate_restricted_tam_dsn
    return _validate_restricted_tam_dsn(
        content, login="empire_tam_market_login"
    )
