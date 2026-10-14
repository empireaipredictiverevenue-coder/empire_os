"""Bounded, no-follow original-message custody inspection for Postfix Maildir.

This proves only that a designated original RFC message exists in a protected
local Maildir at the instant checked. The stored bytes are NOT guaranteed to
match SMTP wire bytes (Postfix adds Received and other transport headers).
It does not prove the SMTP sender, DKIM/SPF/DMARC, MTA queue identity, tenant,
contact, consent, suppression, production readiness or buyer intent.

Stage-only: no network, database, outbound send, key, secret or file writes.
"""
from __future__ import annotations

from email.parser import BytesHeaderParser
from email.policy import default
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from typing import Any
from uuid import UUID

MAX_DELIVERED_BYTES = 512 * 1024
MAX_HEADER_BYTES = 48 * 1024
FIXTURE_ID = str(UUID(int=121))
FIXTURE_MAILBOX = f"jev-{FIXTURE_ID}"
ROOT_NAME = re.compile(r"^empire-postfix-stage-[A-Za-z0-9_-]{4,48}$")
HEX = re.compile(r"^[0-9a-f]{64}$")


def _regular_secure(path: Path, *, uid: int | None = None, size_limit: int = MAX_DELIVERED_BYTES) -> bytes:
    if path.is_symlink():
        raise ValueError("symbolic link forbidden")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("no-follow filesystem required")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ValueError("protected maildir entry unavailable") from None
    try:
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or not 0 < before.st_size <= size_limit or
                (uid is not None and before.st_uid != uid)
                or stat.S_IMODE(before.st_mode) & 0o022):
            raise ValueError("unsafe maildir file owner, type, size or link count")
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            raw = stream.read(size_limit + 1)
        after = os.fstat(descriptor)
        if (len(raw) != before.st_size or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("maildir file mutated during read")
        return raw
    finally:
        os.close(descriptor)


def _inspect_fixture_maildir_custody(
    stage_root: Path, *,
    expected_rfc_message_id: str,
    expected_recipient: str,
    expected_body_marker: str,
    previous_sha256: str | None,
    root_uid: int,
    mail_uid: int,
) -> dict[str, Any]:
    """Internal fixture seam; public operator fixes IDs to root/15000."""
    if not isinstance(stage_root, Path) or not stage_root.is_absolute():
        raise ValueError("absolute staging root required")
    if (stage_root.parent != Path("/tmp") or not ROOT_NAME.fullmatch(stage_root.name)
            or stage_root.is_symlink()):
        raise ValueError("isolated staging root required")
    root_stat = stage_root.lstat()
    if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != root_uid:
        raise ValueError("owner-controlled staging root required")
    marker = stage_root / ".empire-ci-mail-delivery-test"
    if _regular_secure(marker, uid=root_uid, size_limit=96) != b"CI_CONTAINER_NETWORK_NONE\n":
        raise ValueError("invalid trusted test marker")
    if previous_sha256 is not None and (
        not isinstance(previous_sha256, str) or not HEX.fullmatch(previous_sha256)
    ):
        raise ValueError("canonical prior SHA256 expected")
    if (not isinstance(expected_rfc_message_id, str)
            or not expected_rfc_message_id.startswith("<")
            or not expected_rfc_message_id.endswith(">")
            or len(expected_rfc_message_id) > 256
            or not isinstance(expected_body_marker, str)
            or not re.fullmatch(r"EMPIRE_SYNTHETIC_[A-Z0-9_]{1,80}", expected_body_marker)
            or expected_recipient != f"reply+{FIXTURE_ID}@mail.empire-ai.co.uk"):
        raise ValueError("exact synthetic RFC fixture authority required")

    parent = stage_root / "maildir"
    mailbox = parent / FIXTURE_MAILBOX
    for directory, uid in ((parent, mail_uid), (mailbox, mail_uid)):
        if directory.is_symlink():
            raise ValueError("maildir symlink refused")
        st = directory.lstat()
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != uid
                or stat.S_IMODE(st.st_mode) & 0o022):
            raise ValueError("maildir owner or mode untrusted")

    entries: list[Path] = []
    for name in ("new", "cur", "tmp"):
        directory = mailbox / name
        if directory.is_symlink():
            raise ValueError("maildir subdirectory symlink refused")
        st = directory.lstat()
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != mail_uid
                or stat.S_IMODE(st.st_mode) & 0o022):
            raise ValueError("maildir subdirectory ownership untrusted")
        files = list(directory.iterdir())
        if name == "tmp" and files:
            raise ValueError("incomplete Maildir temporary delivery")
        if name != "tmp":
            entries.extend(files)
    if len(entries) != 1:
        raise ValueError("exactly one delivered Maildir entry expected")
    raw = _regular_secure(entries[0], uid=mail_uid)
    digest = sha256(raw).hexdigest()
    if previous_sha256 is not None and digest != previous_sha256:
        raise ValueError("Maildir changed since recorded custody event")

    cut = raw.find(b"\n\n")
    if cut < 0:
        cut = raw.find(b"\r\n\r\n")
    if cut < 0 or cut > MAX_HEADER_BYTES:
        raise ValueError("unbounded stored RFC header section")
    parsed = BytesHeaderParser(policy=default).parsebytes(raw[:cut+4])
    if parsed.defects:
        raise ValueError("stored RFC header parser defects")
    if any(parsed.get_all(header, []) for header in (
        "Authentication-Results", "ARC-Authentication-Results", "Received-SPF"
    )):
        raise ValueError("unverified sender-authentication header survived staging")
    if len(parsed.get_all("Message-ID", [])) != 1:
        raise ValueError("ambiguous Message-ID in stored RFC")
    if str(parsed["Message-ID"]) != expected_rfc_message_id:
        raise ValueError("original synthetic Message-ID not preserved")
    if not expected_recipient.encode("ascii") in raw[:MAX_HEADER_BYTES]:
        raise ValueError("original synthetic recipient not preserved")
    if expected_body_marker.encode("ascii") not in raw[cut:]:
        raise ValueError("synthetic message marker not preserved")

    return {
        "schema_version": "empire.mail.offline_maildir_custody.v1",
        "mode": "ISOLATED_SYNTHETIC_ONLY",
        "status": "ORIGINAL_STORED_RFC_CUSTODY_VERIFIED",
        "maildir_item_count": 1,
        "stored_rfc_bytes_sha256": digest,
        "stored_size_bytes": len(raw),
        "original_message_id_present": True,
        "synthetic_recipient_present": True,
        "synthetic_body_preserved": True,
        "previous_digest_unchanged": previous_sha256 is not None,
        "original_smtp_wire_digest_verified": False,
        "mta_queue_log_binding_verified": False,
        "dkim_spf_dmarc_authenticated": False,
        "untrusted_authentication_headers_absent": True,
        "trusted_mta_auth_verifier_deployed": False,
        "sender_identity_verified": False,
        "canonical_contact_verified": False,
        "customer_mail_received": False,
        "data_sent_by_probe": False,
        "production_mx_changed": False,
        "execution_authority": "fixture-only",
    }



def inspect_fixture_maildir_custody(
    stage_root: Path, *,
    expected_rfc_message_id: str,
    expected_recipient: str,
    expected_body_marker: str,
    previous_sha256: str | None = None,
) -> dict[str, Any]:
    """Fixed, independently designated owner IDs for offline container only."""
    return _inspect_fixture_maildir_custody(
        stage_root,
        expected_rfc_message_id=expected_rfc_message_id,
        expected_recipient=expected_recipient,
        expected_body_marker=expected_body_marker,
        previous_sha256=previous_sha256,
        root_uid=0,
        mail_uid=15000,
    )
