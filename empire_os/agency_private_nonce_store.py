"""Durable single-node replay receipts for approved agency signing grants.

Fail-closed, owner-private, exclusive-create local files. This is NOT a
multi-host distributed replay database, nor a production deployment.
Owner provisions and protects the directory; only validated jti strings enter.
"""
from __future__ import annotations
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

_JTI = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


@dataclass(frozen=True)
class PrivateAgencyNonceStore:
    directory: Path
    trusted_uid: int

    def __call__(self, token_id: str) -> bool:
        if not isinstance(token_id, str) or not _JTI.fullmatch(token_id):
            return False
        if (not isinstance(self.directory, Path) or not self.directory.is_absolute()
                or type(self.trusted_uid) is not int or self.trusted_uid < 0):
            return False
        try:
            # Open the directory itself without following a replaced symlink.
            dirfd = os.open(self.directory,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                meta = os.fstat(dirfd)
                if (not stat.S_ISDIR(meta.st_mode)
                        or meta.st_uid != self.trusted_uid or meta.st_mode & 0o077):
                    return False
                name = hashlib.sha256(
                    b"empire-agency-replay-v1:" + token_id.encode("ascii")
                ).hexdigest()
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600, dir_fd=dirfd,
                )
                try:
                    st = os.fstat(fd)
                    if (not stat.S_ISREG(st.st_mode) or st.st_uid != self.trusted_uid
                            or st.st_mode & 0o077):
                        return False
                    os.write(fd, b"empire-agency-replay-v1\\n")
                    os.fsync(fd)
                    os.fsync(dirfd)
                finally:
                    os.close(fd)
            finally:
                os.close(dirfd)
            return True
        except OSError:
            # Duplicate files, permission failures, read-only mount, disk full,
            # or unexpected link/path state all deny access.
            return False
