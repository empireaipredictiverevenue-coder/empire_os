#!/usr/bin/env python3
"""One missing DIRECT BSC verifier: reviewed HBA rule then segregated SQL LOGIN.

Three explicit operations:
  --preflight: READ ONLY.
  --apply-hba --approved-one-direct-verifier-scram-rule: exact HBA + reload.
  --apply-login --approved-one-direct-verifier-login: exact LOGIN, membership,
      database CONNECT, root-only secret, independent password authentication.
No wallet, transaction, checkout flags, payment evidence or customer records.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from scripts import deploy_crm_hba_three_roles as prior
from scripts import provision_bsc_financial_operator_logins as existing
from scripts.provision_crm_dedicated_logins import scram_verifier
from scripts.inspect_direct_bsc_verifier_readiness import inspect, GROUP, LOGIN, DB

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "scripts/activate_direct_bsc_verifier_identity.py"
VAULT = existing.VAULT
PASSFILE = VAULT / (LOGIN + ".pgpass")
LOCK = Path("/run/lock/empire-direct-verifier-identity.lock")
HBA_BACKUP = Path("/var/backups/empiredb/direct-verifier-hba")
ROLE_BACKUP = Path("/var/backups/empiredb/direct-verifier-role")
MARKER = "# BEGIN EMPIRE_DIRECT_BSC_VERIFIER_V1"
RULE = (
    MARKER + "\n"
    "local   empiredb   empire_bsc_verifier_login   scram-sha-256\n"
    "# END EMPIRE_DIRECT_BSC_VERIFIER_V1\n"
)


def additive_hba(original: bytes) -> bytes:
    if not isinstance(original, bytes) or not original or b"\x00" in original or b"\r" in original:
        raise ValueError("unexpected HBA encoding")
    content = original.decode("utf-8", "strict")
    if "EMPIRE_DIRECT_BSC_VERIFIER_V1" in content:
        raise ValueError("existing direct verifier HBA marker")
    for line in content.splitlines():
        active = line.split("#", 1)[0].split()
        if len(active) >= 3 and LOGIN in active[2].split(","):
            raise ValueError("preexisting direct verifier HBA entry")
    return RULE.encode("ascii") + original


def _committed_source() -> None:
    def git(*args):
        return subprocess.run(["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT),
                               *args], check=True, capture_output=True, text=True,
                              timeout=6).stdout.strip()
    try:
        if (git("status", "--porcelain", "--", SOURCE) or
                git("hash-object", str(ROOT / SOURCE)) !=
                git("rev-parse", "HEAD:" + SOURCE)):
            raise RuntimeError()
    except Exception:
        raise RuntimeError("direct verifier identity source not committed and clean") from None


def _postgres_child(mode: str, payload: dict | None = None) -> dict:
    if mode not in ("--internal-inspect", "--internal-create"):
        raise RuntimeError("unsupported postgres operation")
    p = subprocess.run(
        ["runuser", "-u", "postgres", "--", sys.executable, "-m",
         "scripts.activate_direct_bsc_verifier_identity", mode],
        input=None if payload is None else json.dumps(payload),
        capture_output=True, text=True, cwd=ROOT, timeout=25,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH": str(ROOT), "HOME": "/var/lib/postgresql",
            "PGHOST": existing.SOCKET, "PGPORT": "5432", "PGDATABASE": DB,
        },
    )
    if p.returncode:
        raise RuntimeError("canonical postgres verifier operation failed")
    return json.loads(p.stdout)


def _secure_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.lstat()
    if path.is_symlink() or not path.is_dir() or st.st_uid != 0 or (st.st_mode & 0o777) != 0o700:
        raise RuntimeError("root-only backup directory invariant failed")


def _backup_bytes(base: Path, name: str, data: bytes) -> Path:
    _secure_dir(base)
    folder = base / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(mode=0o700)
    target = folder / name
    fd = os.open(target, os.O_EXCL | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    digest = hashlib.sha256(data).hexdigest()
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise RuntimeError("backup checksum mismatch")
    (folder / "SHA256").write_text(digest + "  " + name + "\n")
    os.chmod(folder / "SHA256", 0o600)
    return folder


def _backup_globals() -> Path:
    p = subprocess.run(
        ["runuser", "-u", "postgres", "--", "pg_dumpall", "-w", "-h",
         existing.SOCKET, "-p", "5432", "-U", "postgres", "--globals-only"],
        capture_output=True, timeout=75,
        env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
             "HOME": "/var/lib/postgresql", "PGHOST": existing.SOCKET,
             "PGPORT": "5432", "PGDATABASE": DB},
    )
    if p.returncode or len(p.stdout) < 50:
        raise RuntimeError("global role backup unavailable")
    return _backup_bytes(ROLE_BACKUP, "globals-before.sql", p.stdout)


def _base_safe(report: dict) -> bool:
    return (report.get("status") == "DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED"
            and report.get("canonical_empiredb") is True
            and report.get("permission_role_safe") is True
            and report.get("app_financial_separation_verified") is True
            and report.get("exact_direct_payment_rpc_grants") is True
            and report.get("login_present") is False)


def _vault_safe() -> bool:
    if not VAULT.is_dir() or VAULT.is_symlink():
        return False
    stat = VAULT.stat()
    if (stat.st_uid, stat.st_gid, stat.st_mode & 0o777) != (0, 0, 0o700):
        return False
    for other in existing.NAMES:
        p = VAULT / (other + ".pgpass")
        if p.is_symlink() or not p.is_file():
            return False
        st = p.stat()
        if (st.st_uid, st.st_gid, st.st_mode & 0o777) != (0, 0, 0o600):
            return False
    return not PASSFILE.exists() and not PASSFILE.is_symlink()


def _create_identity(payload: dict) -> dict:
    verifier = payload.get("scram_verifier")
    if (not isinstance(verifier, str) or not verifier.startswith("SCRAM-SHA-256$4096:")
            or len(verifier) > 220):
        raise RuntimeError("unexpected SCRAM verifier")
    report = inspect()
    if not _base_safe(report) or report["effective_local_scram"] is not True:
        raise RuntimeError("direct verifier preflight drift")
    from psycopg import sql
    with existing._db() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='12000ms'")
        cur.execute("SET LOCAL lock_timeout='3000ms'")
        cur.execute(sql.SQL(
            "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(sql.Identifier(LOGIN), sql.Literal(verifier)))
        cur.execute(sql.SQL(
            "GRANT {} TO {} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
        ).format(sql.Identifier(GROUP), sql.Identifier(LOGIN)))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(DB), sql.Identifier(LOGIN)))
    after = inspect()
    if after["status"] != "DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED":
        raise RuntimeError("post-commit direct verifier catalog held")
    return {"state": "DIRECT_VERIFIER_SQL_IDENTITY_CREATED", "checkout_activated": False}


def _verify_login(password: str) -> None:
    import psycopg
    from psycopg import sql
    with psycopg.connect(host=existing.SOCKET, port=5432, dbname=DB,
                         user=LOGIN, password=password, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT session_user,current_user,current_database()")
        if cur.fetchone() != (LOGIN, LOGIN, DB):
            raise RuntimeError("wrong identity")
        cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(GROUP)))
        cur.execute("SELECT session_user,current_user")
        if cur.fetchone() != (LOGIN, GROUP):
            raise RuntimeError("role activation mismatch")
        conn.rollback()
    for denied in ("empire_payment_approver", "empire_escrow_verifier"):
        try:
            with psycopg.connect(host=existing.SOCKET, port=5432, dbname=DB,
                                 user=LOGIN, password=password, connect_timeout=5) as conn, conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(denied)))
            raise RuntimeError("financial cross-role escalation")
        except psycopg.errors.InsufficientPrivilege:
            pass
    try:
        with psycopg.connect(host=existing.SOCKET, port=5432, dbname=DB,
                             user=LOGIN, password="wrong-direct-verifier-password",
                             connect_timeout=5) as conn:
            pass
        raise RuntimeError("wrong password accepted")
    except psycopg.OperationalError:
        pass


def _root_main(flags: list[str]) -> int:
    choices = (
        ["--preflight"],
        ["--apply-hba", "--approved-one-direct-verifier-scram-rule"],
        ["--apply-login", "--approved-one-direct-verifier-login"],
    )
    if flags not in choices or os.geteuid() != 0:
        print("DIRECT_VERIFIER_STATUS=HELD_EXACT_ROOT_FLAGS_REQUIRED")
        return 3
    try:
        with LOCK.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            prior.cluster_guard()
            report = _postgres_child("--internal-inspect")
            if not _base_safe(report):
                print("DIRECT_VERIFIER_STATUS=HELD_EXISTING_CATALOG_OR_AUTHORITY_DRIFT")
                return 2
            if flags == ["--preflight"]:
                print(json.dumps({
                    "status": report["status"],
                    "mode": "READ_ONLY",
                    "hba_prepared": report["effective_local_scram"],
                    "existing_operator_vault_safe": _vault_safe(),
                    "payment_activated": False,
                    "next_gate": ("LOGIN_APPROVAL" if report["effective_local_scram"]
                                  else "HBA_APPROVAL"),
                }, sort_keys=True))
                return 0
            _committed_source()
            if flags[0] == "--apply-hba":
                if report["effective_local_scram"]:
                    print("DIRECT_VERIFIER_STATUS=ALREADY_HBA_READY_NO_CHANGE")
                    return 0
                st, old = prior.owner_and_content()
                new = additive_hba(old)
                previous = prior.invoke_psql(statement="SELECT pg_conf_load_time()")
                backup = _backup_bytes(HBA_BACKUP, "pg_hba.conf.before", old)
                print("DIRECT_VERIFIER_HBA_BACKUP_SHA256_VERIFIED=YES")
                print("DIRECT_VERIFIER_HBA_BACKUP_DIRECTORY=" + str(backup))
                if prior.HBA.read_bytes() != old:
                    raise RuntimeError("concurrent HBA file change")
                prior.atomic_write_hba(new, st)
                try:
                    prior.reload()
                    import time
                    for _ in range(12):
                        new_report = _postgres_child("--internal-inspect")
                        if (_base_safe(new_report) and new_report["effective_local_scram"]
                                and prior.invoke_psql(statement="SELECT pg_conf_load_time()") != previous):
                            print("DIRECT_VERIFIER_HBA_STATUS=EXACT_ONE_SCRAM_RULE_VERIFIED")
                            print("DIRECT_VERIFIER_LOGIN_CREATED=NO")
                            return 0
                        time.sleep(.2)
                    raise RuntimeError("HBA reload proof held")
                except Exception:
                    if prior.HBA.read_bytes() == new:
                        prior.atomic_write_hba(old, st)
                        prior.reload()
                        print("DIRECT_VERIFIER_HBA_ROLLBACK=ORIGINAL_RESTORED")
                    raise
            if not report["effective_local_scram"] or not _vault_safe():
                print("DIRECT_VERIFIER_STATUS=HELD_HBA_OR_PRIVATE_VAULT_UNREADY")
                return 2
            backup = _backup_globals()
            print("DIRECT_VERIFIER_GLOBAL_ROLES_BACKUP_SHA256_VERIFIED=YES")
            print("DIRECT_VERIFIER_ROLE_BACKUP_DIRECTORY=" + str(backup))
            password = secrets.token_urlsafe(48)
            if len(password) < 48:
                raise RuntimeError("secure random credential unavailable")
            value = f"{existing.SOCKET}:5432:{DB}:{LOGIN}:{password}\n"
            fd = os.open(PASSFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(value); f.flush(); os.fsync(f.fileno())
            try:
                _postgres_child("--internal-create", {"scram_verifier": scram_verifier(password)})
            except Exception:
                if _base_safe(_postgres_child("--internal-inspect")):
                    PASSFILE.unlink()
                    print("DIRECT_VERIFIER_UNCOMMITTED_CREDENTIAL_ROLLBACK=YES")
                raise
            after = _postgres_child("--internal-inspect")
            if after["status"] != "DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED":
                raise RuntimeError("postcommit catalog drift")
            _verify_login(password)
            print("DIRECT_VERIFIER_AUTH_SET_ROLE_AND_CROSS_ROLE_DENIAL=PASS")
            print("DIRECT_VERIFIER_HUMAN_ASSIGNMENT=STILL_GATED")
            print("DIRECT_VERIFIER_CHECKOUT_PAYMENT_ACTIVATED=NO")
            print("DIRECT_VERIFIER_STATUS=EXACT_ONE_LOGIN_PROVISIONED")
            return 0
    except Exception:
        print("DIRECT_VERIFIER_STATUS=HELD_NO_BLIND_RETRY_REQUIRES_RECONCILIATION")
        return 4


def main() -> int:
    flags = sys.argv[1:]
    if flags in (["--internal-inspect"], ["--internal-create"]):
        import pwd
        if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
            return 3
        try:
            if flags == ["--internal-inspect"]:
                print(json.dumps(inspect(), sort_keys=True))
            else:
                print(json.dumps(_create_identity(json.load(sys.stdin)), sort_keys=True))
            return 0
        except Exception:
            return 4
    return _root_main(flags)


if __name__ == "__main__":
    raise SystemExit(main())
