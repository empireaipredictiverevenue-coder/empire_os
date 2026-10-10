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
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_mode & 0o077
            or not 10 <= path.stat().st_size <= 2048):
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
