"""Read a Scaleway Secret Manager token only from scoped systemd credentials.

The future, separately reviewed customer OAuth service must use:
LoadCredential=scaleway-secret-iam-token:/root/private/approved-token-source

The currently running DARK staging service has no LoadCredential and cannot
access this capability. Never use generic SCW_SECRET_KEY or repo/env secrets.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from empire_os.inbound_google_calendar_adapter import CalendarVerificationError

CREDENTIAL_NAME = "scaleway-secret-iam-token"
SYSTEMD_SERVICE = "empire-inbound-recovery-calendar-oauth.service"
PRODUCTION_DIRECTORY = Path("/run/credentials") / SYSTEMD_SERVICE


def read_calendar_secret_manager_iam_token(
    *, credential_directory: Path | None = None,
) -> str:
    if credential_directory is None:
        delivered = os.environ.get("CREDENTIALS_DIRECTORY")
        if delivered != str(PRODUCTION_DIRECTORY):
            raise CalendarVerificationError("calendar_secret_iam_runtime_not_provisioned")
        directory = PRODUCTION_DIRECTORY
        systemd_delivered = True
    else:
        directory = Path(credential_directory)
        # Explicit directory only for operator provisioning checks and
        # tests. It must remain private and owner controlled.
        systemd_delivered = (
            directory == PRODUCTION_DIRECTORY
            and os.environ.get("CREDENTIALS_DIRECTORY") == str(PRODUCTION_DIRECTORY)
        )
    if (not directory.is_absolute() or directory.is_symlink()
        or not directory.is_dir()):
        raise CalendarVerificationError("calendar_secret_iam_directory_untrusted")
    path = directory / CREDENTIAL_NAME
    if path.is_symlink() or not path.is_file():
        raise CalendarVerificationError("calendar_secret_iam_not_found")
    directory_mode = stat.S_IMODE(directory.stat().st_mode)
    credential_mode = stat.S_IMODE(path.stat().st_mode)
    if systemd_delivered:
        # Systemd's mounted credential copy can have group/public read bits
        # inside a private directory. It must not be writable and the
        # directory cannot be traversed by unrelated principals.
        unsafe = bool(credential_mode & 0o222) or bool(directory_mode & 0o007)
    else:
        unsafe = bool(credential_mode & 0o077) or bool(directory_mode & 0o077)
    if unsafe or not 20 <= path.stat().st_size <= 1025:
        raise CalendarVerificationError("calendar_secret_iam_permissions_denied")
    try:
        value = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        raise CalendarVerificationError("calendar_secret_iam_unreadable") from None
    if (not 20 <= len(value) <= 1024 or not value.isascii()
        or any(c.isspace() for c in value)):
        raise CalendarVerificationError("calendar_secret_iam_invalid")
    return value
