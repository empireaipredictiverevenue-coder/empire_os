"""Read a named agency connector secret from trusted, private credential directory.

Compatible with a separately provisioned systemd LoadCredential-style file
delivery; this module DOES NOT create a vault, provision production credentials,
register a systemd unit, or fall back to env secrets.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

_ALLOWED_REF = re.compile(r"^[a-z][a-z0-9-]{5,95}$")


def read_private_connector_password(
    *, trusted_directory: Path, credential_ref: str, trusted_uid: int,
) -> str:
    """Resolve one explicitly authorised secret, with no symlink/path traversal.

    For the future systemd read-only credential mount, the trust owner should
    separately validate its fixed unit path and uid. This staging adapter
    deliberately accepts only owner-only files/dirs, never global fallbacks.
    """
    if (not isinstance(trusted_directory, Path)
            or not isinstance(credential_ref, str)
            or not _ALLOWED_REF.fullmatch(credential_ref)
            or type(trusted_uid) is not int or trusted_uid < 0):
        raise ValueError("Approved connector credential reference required")
    try:
        dstat = trusted_directory.lstat()
        if (not stat.S_ISDIR(dstat.st_mode) or dstat.st_uid != trusted_uid
                or dstat.st_mode & 0o077):
            raise ValueError()
        source = trusted_directory / credential_ref
        fstat = source.lstat()
        if (not stat.S_ISREG(fstat.st_mode) or fstat.st_uid != trusted_uid
                or fstat.st_mode & 0o177 or fstat.st_size < 20
                or fstat.st_size > 512):
            raise ValueError()
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode)
                    or (opened.st_dev, opened.st_ino) != (fstat.st_dev, fstat.st_ino)
                    or opened.st_uid != trusted_uid
                    or opened.st_mode & 0o177
                    or opened.st_size != fstat.st_size):
                raise ValueError()
            data = os.read(fd, 513)
        finally:
            os.close(fd)
        if len(data) != fstat.st_size:
            raise ValueError()
        password = data.decode("ascii").strip()
        if (not 20 <= len(password) <= 256
                or not re.fullmatch(r"[A-Za-z0-9 ]+", password)
                or any(c in password for c in ("\r", "\n", "\x00"))):
            raise ValueError()
        return password
    except (OSError, ValueError, UnicodeError):
        # Do not include secret path or credential bytes in errors.
        raise ValueError("Approved connector credential unavailable or unsafe") from None
