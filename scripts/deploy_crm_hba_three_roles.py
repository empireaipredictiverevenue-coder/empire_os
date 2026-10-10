#!/usr/bin/env python3
"""One-time, separately founder-approved HBA amendment for 3 CRM identities.

No role/password/database, HTTP, email, campaign or service activation here.
This must run as an authorised root operator, never by an unprivileged agent.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PRECHECK = ROOT / "scripts/probe_crm_first_login_auth_readonly.sql"
HBA = Path("/etc/postgresql/18/main/pg_hba.conf")
DATA = "/var/lib/postgresql/18/main"
BACKUPS = Path("/var/backups/empiredb/crm-founder-hba-three-roles")
LOCK = Path("/run/lock/empire-crm-hba-three-roles.lock")

RULES = (
    "local   empiredb   empire_crm_auth_login             scram-sha-256\n"
    "local   empiredb   empire_crm_membership_login       scram-sha-256\n"
    "local   empiredb   empire_crm_tenant_708efd4b53b2   scram-sha-256\n"
)
HEADER = (
    "# BEGIN EMPIRE_CRM_FOUNDER_THREE_LOGINS_V1\n"
    "# Exact database/roles, first-match SCRAM only; do not change other HBA rules.\n"
    + RULES +
    "# END EMPIRE_CRM_FOUNDER_THREE_LOGINS_V1\n"
)
MARKER = "BEGIN EMPIRE_CRM_FOUNDER_THREE_LOGINS_V1"


def amended(original: bytes) -> bytes:
    """Pure, additive, reversible transformation. Existing bytes unchanged."""
    if not isinstance(original, bytes) or not original.strip():
        raise ValueError("missing existing HBA")
    if MARKER.encode() in original or b"\x00" in original:
        raise ValueError("HBA already patched or malformed")
    if b"\r" in original:
        raise ValueError("unknown HBA line endings")
    return HEADER.encode("ascii") + original


def invoke_psql(*, filename: Path | None = None, statement: str | None = None) -> str:
    args = [
        "runuser", "-u", "postgres", "--", "psql", "-X", "-w", "-q", "-At",
        "-v", "ON_ERROR_STOP=1", "-d", "empiredb",
    ]
    if filename:
        args.extend(("-f", str(filename)))
    elif statement:
        args.extend(("-c", statement))
    else:
        raise ValueError("a bounded read-only statement required")
    result = subprocess.run(args, capture_output=True, text=True, timeout=18)
    if result.returncode:
        raise RuntimeError("canonical PostgreSQL catalog read/reload unavailable")
    return result.stdout.strip()


def readiness() -> dict:
    return json.loads(invoke_psql(filename=PRECHECK))


def reviewed_release_guard() -> None:
    """Production apply requires the exact checked-in, unmodified source."""
    relative = Path("scripts/deploy_crm_hba_three_roles.py")
    try:
        index = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), "status", "--porcelain", "--", str(relative)],
            capture_output=True, text=True, timeout=5, check=True,
        )
        current = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), "hash-object", str(ROOT / relative)],
            capture_output=True, text=True, timeout=5, check=True,
        )
        expected = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), "rev-parse", "HEAD:" + str(relative)],
            capture_output=True, text=True, timeout=5, check=True,
        )
        if index.stdout.strip() or current.stdout.strip() != expected.stdout.strip():
            raise RuntimeError("uncommitted source or reviewed release mismatch")
    except Exception:
        raise RuntimeError("unreviewed CRM HBA deployment source") from None


def cluster_guard() -> None:
    if subprocess.run(
        ["systemctl", "is-active", "--quiet", "postgresql@18-main.service"],
        capture_output=True, timeout=5,
    ).returncode:
        raise RuntimeError("canonical PostgreSQL 18 service unavailable")
    rows = invoke_psql(
        statement="SELECT current_database()||'|'||current_setting('data_directory')"
                  "||'|'||current_setting('hba_file')||'|'||pg_is_in_recovery()"
    )
    if rows != f"empiredb|{DATA}|{HBA}|false":
        raise RuntimeError("noncanonical PostgreSQL cluster")


def owner_and_content() -> tuple[os.stat_result, bytes]:
    if HBA.is_symlink() or not HBA.is_file():
        raise RuntimeError("unexpected HBA file path")
    st = HBA.stat()
    if not stat.S_ISREG(st.st_mode):
        raise RuntimeError("HBA not regular file")
    postgres = pwd.getpwnam("postgres")
    if st.st_uid != postgres.pw_uid or (stat.S_IMODE(st.st_mode) & 0o027):
        raise RuntimeError("HBA ownership/permissions unsafe")
    return st, HBA.read_bytes()


def atomic_write_hba(payload: bytes, st: os.stat_result) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".crm-hba-", dir=HBA.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(tmp, st.st_uid, st.st_gid)
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        os.replace(tmp, HBA)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def backup(original: bytes) -> Path:
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = BACKUPS / stamp
    folder.mkdir(mode=0o700)
    path = folder / "pg_hba.conf.before"
    with path.open("xb") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    digest = hashlib.sha256(original).hexdigest()
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError("HBA backup mismatch")
    (folder / "SHA256").write_text(digest + "  pg_hba.conf.before\n")
    os.chmod(folder / "SHA256", 0o600)
    return folder


def reload() -> None:
    if invoke_psql(statement="SELECT pg_reload_conf()") != "t":
        raise RuntimeError("PostgreSQL reload rejected")


def verify_expected_catalog() -> bool:
    try:
        data = readiness()
        return (
            data.get("canonical_database") is True
            and data.get("active_founder_owner_verified") is True
            and data.get("existing_identity_roles_staged") is True
            and data.get("tenant_reader_role_not_created") is True
            and data.get("tenant_reader_binding_not_created") is True
            and data.get("hba_configuration_parses") is True
            and data.get("all_three_role_specific_scram_rules_effective") is True
            and data.get("next_action") == "READY_FOR_APPROVED_THREE_LOGIN_PROVISIONING"
        )
    except Exception:
        return False


def main() -> int:
    argv = sys.argv[1:]
    approved = argv == ["--apply", "--approved-exact-three-crm-hba-rules"]
    if argv not in (["--preflight"], ["--apply", "--approved-exact-three-crm-hba-rules"]):
        print("CRM_HBA_RESULT=BLOCKED_EXACT_FLAGS_REQUIRED")
        return 3
    if os.geteuid() != 0:
        print("CRM_HBA_RESULT=BLOCKED_ROOT_OPERATOR_REQUIRED")
        return 3
    try:
        with LOCK.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            cluster_guard()
            st, original = owner_and_content()
            plan = readiness()
            if plan.get("next_action") == "READY_FOR_APPROVED_THREE_LOGIN_PROVISIONING":
                print("CRM_HBA_RESULT=ALREADY_READY_NO_CHANGE")
                return 0
            if not (
                plan.get("next_action") == "PREPARE_EXACT_LOCAL_SCRAM_AUTH_RULES"
                and plan.get("active_founder_owner_verified") is True
                and plan.get("existing_identity_roles_staged") is True
                and plan.get("hba_configuration_parses") is True
                and plan.get("tenant_reader_role_not_created") is True
                and plan.get("tenant_reader_binding_not_created") is True
            ):
                print("CRM_HBA_RESULT=BLOCKED_CATALOG_PREREQUISITES")
                return 2
            patched = amended(original)
            print("CRM_HBA_SCOPE=EXACT_THREE_LOCAL_EMPIREDB_SCRAM_RULES")
            print("CRM_HBA_OTHER_RULES_PRESERVED=YES")
            if not approved:
                print("CRM_HBA_RESULT=PREFLIGHT_READY_NO_CHANGE")
                return 0
            reviewed_release_guard()
            previous_config_loaded_at = invoke_psql(statement="SELECT pg_conf_load_time()")
            folder = backup(original)
            print("CRM_HBA_BACKUP_SHA256=VERIFIED")
            print("CRM_HBA_BACKUP_LOCATION=" + str(folder))
            # Detect independent HBA edits before the atomic replace.
            if HBA.read_bytes() != original or HBA.is_symlink():
                raise RuntimeError("concurrent HBA edit")
            atomic_write_hba(patched, st)
            try:
                reload()
                for _ in range(12):
                    if (verify_expected_catalog()
                            and invoke_psql(statement="SELECT pg_conf_load_time()")
                                != previous_config_loaded_at):
                        print("CRM_HBA_POST_RELOAD=THREE_EXACT_RULES_VERIFIED")
                        print("CRM_HBA_ROLES_OR_PASSWORDS_CHANGED=NO")
                        print("CRM_HBA_PUBLIC_API_OR_OUTBOUND_CHANGED=NO")
                        print("CRM_HBA_RESULT=APPROVED_EXACT_RULES_ACTIVATED")
                        return 0
                    time.sleep(0.2)
                raise RuntimeError("post-reload auth policy not verified")
            except Exception:
                # Only restore if the file is still our exact amended bytes:
                # never overwrite concurrent operator changes.
                if HBA.read_bytes() == patched:
                    atomic_write_hba(original, st)
                    try:
                        reload()
                        print("CRM_HBA_ROLLBACK=ORIGINAL_FILE_RESTORED")
                    except Exception:
                        print("CRM_HBA_ROLLBACK=UNVERIFIED_MANUAL_RECONCILIATION_REQUIRED")
                else:
                    print("CRM_HBA_ROLLBACK=WITHHELD_CONCURRENT_CHANGE")
                raise
    except Exception:
        print("CRM_HBA_RESULT=BLOCKED_OR_UNVERIFIED_DO_NOT_BLINDLY_RETRY")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
