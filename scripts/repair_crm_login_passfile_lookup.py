#!/usr/bin/env python3
"""Bounded recovery of an existing, committed three-login CRM SCRAM passfile.

Never modifies database roles, passwords, tenant bindings, membership, HBA,
service configuration or network exposure. Never prints secret material.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile

DIR = Path("/var/lib/empire-crm-first-party")
PASSFILE = DIR / "pgpass"
BACKUP = DIR / ".pgpass.before-localhost-repair"
LOCK = DIR / ".pgpass-repair.lock"
SOCKET = "/var/run/postgresql"
TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"
ROLES = (
    "empire_crm_auth_login",
    "empire_crm_membership_login",
    "empire_crm_tenant_708efd4b53b2",
)
HOSTS = (SOCKET, "localhost")


def _validate_permissions() -> None:
    account = pwd.getpwnam("ubuntu")
    if DIR.is_symlink() or PASSFILE.is_symlink() or not DIR.is_dir() or not PASSFILE.is_file():
        raise ValueError("CRM passfile is unavailable or not a regular private file")
    parent = DIR.stat()
    current = PASSFILE.stat()
    if (parent.st_uid != account.pw_uid or stat.S_IMODE(parent.st_mode) != 0o700
            or current.st_uid != account.pw_uid
            or stat.S_IMODE(current.st_mode) != 0o600):
        raise ValueError("CRM credential file ownership or permissions incorrect")


def inspect(payload: bytes) -> str:
    """No secrets returned. Original three and repaired six rows only."""
    try:
        if not payload.endswith(b"\n") or b"\r" in payload or b"\x00" in payload:
            return "INVALID"
        lines = [line.split(b":", 4) for line in payload.splitlines()]
        if not lines or any(len(p) != 5 for p in lines):
            return "INVALID"
        keys = {}
        for host, port, db, role, credential in lines:
            if (host.decode("ascii") not in HOSTS or port != b"5432"
                    or db != b"empiredb" or len(credential) < 32
                    or b"\\" in credential or not credential.isascii()):
                return "INVALID"
            name = role.decode("ascii")
            if name not in ROLES or (host, name) in keys:
                return "INVALID"
            keys[(host, name)] = credential
        for role in ROLES:
            if (SOCKET.encode(), role) not in keys:
                return "INVALID"
        expected_base = {(SOCKET.encode(), role) for role in ROLES}
        if set(keys) == expected_base:
            return "ORIGINAL_THREE_ROWS"
        expected_both = {(host.encode(), role) for host in HOSTS for role in ROLES}
        if (set(keys) == expected_both and all(
                keys[(SOCKET.encode(), role)] == keys[(b"localhost", role)]
                for role in ROLES)):
            return "REPAIRED_SIX_ROWS"
        return "INVALID"
    except (ValueError, UnicodeError, AttributeError):
        return "INVALID"


def patched(original: bytes) -> bytes:
    if inspect(original) != "ORIGINAL_THREE_ROWS":
        raise ValueError("unexpected original passfile")
    rows = original.splitlines()
    extra = []
    for line in rows:
        host, port, db, role, credential = line.split(b":", 4)
        if host != SOCKET.encode():
            raise ValueError("original host unexpected")
        extra.append(b":".join((b"localhost", port, db, role, credential)) + b"\n")
    proposed = original + b"".join(extra)
    if inspect(proposed) != "REPAIRED_SIX_ROWS":
        raise ValueError("repaired passfile invalid")
    return proposed


def _write_exclusive(path: Path, payload: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def _replace_contents(payload: bytes):
    fd, temp_name = tempfile.mkstemp(prefix=".crm-pgpass-", dir=DIR)
    try:
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, PASSFILE)
    finally:
        if os.path.lexists(temp_name):
            os.unlink(temp_name)


def _psql(role: str, query: str) -> tuple[int, str]:
    if role not in ROLES:
        raise ValueError("unexpected CRM database role")
    env = dict(os.environ)
    env.pop("PGPASSWORD", None)
    env["PGPASSFILE"] = str(PASSFILE)
    env["PGCONNECT_TIMEOUT"] = "5"
    result = subprocess.run([
        "psql", "-X", "-w", "-q", "-At", "-v", "ON_ERROR_STOP=1",
        "-h", SOCKET, "-p", "5432", "-U", role, "-d", "empiredb", "-c", query
    ], env=env, capture_output=True, text=True, timeout=10)
    # stderr intentionally suppressed: provider errors can reveal environment.
    return result.returncode, result.stdout.strip()


def _verify() -> bool:
    for role in ROLES:
        code, who = _psql(role, "BEGIN READ ONLY; SELECT session_user; ROLLBACK;")
        if code != 0 or who != role:
            return False
    code, tenant = _psql(
        ROLES[2],
        "BEGIN READ ONLY; SET LOCAL ROLE empire_revenue_crm_reader; "
        "SELECT public.empire_current_tenant_id(); ROLLBACK;",
    )
    if code != 0 or tenant != TENANT:
        return False
    # The tenant reader must not read the global role binding table.
    code, _ = _psql(ROLES[2],
        "BEGIN READ ONLY; SELECT 1 FROM public.empire_tenant_role_bindings LIMIT 1; ROLLBACK;")
    if code == 0:
        return False
    return True


def _reviewed_source() -> bool:
    root = Path(__file__).resolve().parents[1]
    relative = "scripts/repair_crm_login_passfile_lookup.py"
    def git(*args: str) -> str:
        p = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return p.stdout.strip()
    try:
        return (not git("status", "--porcelain", "--", relative)
                and git("hash-object", str(Path(__file__).resolve()))
                == git("rev-parse", "HEAD:" + relative))
    except Exception:
        return False


def main() -> int:
    options = (
        ["--preflight"], ["--verify"], ["--apply", "--approved-passfile-lookup-only"],
    )
    if sys.argv[1:] not in options:
        print("CRM_PASSFILE_RESULT=BLOCKED_EXACT_FLAGS_REQUIRED")
        return 3
    if os.geteuid() != pwd.getpwnam("ubuntu").pw_uid:
        print("CRM_PASSFILE_RESULT=BLOCKED_SERVICE_ACCOUNT_REQUIRED")
        return 3
    try:
        _validate_permissions()
        with LOCK.open("a+") as handle:
            os.chmod(LOCK, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            original = PASSFILE.read_bytes()
            state = inspect(original)
            if state == "INVALID":
                print("CRM_PASSFILE_RESULT=BLOCKED_UNEXPECTED_EXISTING_FILE")
                return 2
            if sys.argv[1:] == ["--preflight"]:
                print("CRM_PASSFILE_CONTENT=VALID_PRIVATE_THREE_ROLE_FORMAT")
                print("CRM_PASSFILE_LOOKUP=" + state)
                print("CRM_PASSFILE_RESULT=PREFLIGHT_NO_CHANGES")
                return 0
            if sys.argv[1:] == ["--verify"]:
                if state != "REPAIRED_SIX_ROWS":
                    print("CRM_PASSFILE_RESULT=BLOCKED_LOOKUP_REPAIR_REQUIRED")
                    return 2
                if not _verify():
                    print("CRM_PASSFILE_RESULT=LOGIN_OR_TENANT_PROOF_FAILED")
                    return 4
                print("CRM_PASSFILE_RESULT=THREE_LOGINS_AND_TENANT_PROOF_VERIFIED")
                return 0
            if not _reviewed_source():
                print("CRM_PASSFILE_RESULT=BLOCKED_UNREVIEWED_SOURCE")
                return 2
            if state == "REPAIRED_SIX_ROWS":
                print("CRM_PASSFILE_RESULT=ALREADY_REPAIRED_NO_CHANGES")
                return 0 if _verify() else 4
            if BACKUP.is_symlink():
                raise RuntimeError("private backup symlink unsafe")
            new = patched(original)
            if BACKUP.exists():
                if (not BACKUP.is_file()
                    or BACKUP.stat().st_uid != pwd.getpwnam("ubuntu").pw_uid
                    or stat.S_IMODE(BACKUP.stat().st_mode) != 0o600
                    or BACKUP.read_bytes() != original):
                    raise RuntimeError("old backup does not match original passfile")
                print("CRM_PASSFILE_BACKUP=PREEXISTING_EXACT_MATCH_VERIFIED")
            else:
                _write_exclusive(BACKUP, original)
                print("CRM_PASSFILE_BACKUP=CREATED_EXACT_ORIGINAL")
            if hashlib.sha256(BACKUP.read_bytes()).digest() != hashlib.sha256(original).digest():
                raise RuntimeError("original backup digest incorrect")
            if PASSFILE.read_bytes() != original:
                raise RuntimeError("concurrent passfile modification")
            _replace_contents(new)
            try:
                if not _verify():
                    raise RuntimeError("postfix role or tenant verification failed")
            except Exception:
                if PASSFILE.read_bytes() == new:
                    _replace_contents(original)
                    print("CRM_PASSFILE_ROLLBACK=ORIGINAL_RESTORED")
                else:
                    print("CRM_PASSFILE_ROLLBACK=WITHHELD_CONCURRENT_CHANGE")
                raise
            print("CRM_PASSFILE_SECRET_ROTATION=NO")
            print("CRM_PASSFILE_DATABASE_WRITES=NO")
            print("CRM_PASSFILE_RESULT=THREE_LOGINS_AND_TENANT_PROOF_VERIFIED")
            return 0
    except Exception:
        print("CRM_PASSFILE_RESULT=BLOCKED_OR_UNVERIFIED_DO_NOT_BLINDLY_RETRY")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
