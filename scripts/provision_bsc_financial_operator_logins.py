#!/usr/bin/env python3
"""Provision exactly TWO independently passworded BSC financial SQL logins.

This does not deploy a contract, move funds, approve requests, grant the public
checkout financial permission, or activate payment flags. Two exact dedicated
PostgreSQL logins may SET LOCAL ROLE only their corresponding NOLOGIN group.

READ ONLY by default. --apply requires exact independent founder consent
--approved-two-bsc-financial-operator-logins and verified prior HBA activation.
No password, secret, derived verifier or .pgpass contents are ever printed.

The credential vault is ROOT ONLY. Operational human/Unix-user assignment and
read-only role login tests are additional required gates before live payments.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import secrets
import subprocess
import sys

from empire_os.bsc_payment_operator_readiness import (
    DB, EXPECTED, LOGIN_ROLES, classify,
)
from scripts import prepare_bsc_operator_hba as hba_operator
from scripts.provision_crm_dedicated_logins import scram_verifier

VAULT = Path("/var/lib/empire-bsc-payment-operators")
BACKUPS = Path("/var/backups/empiredb/bsc-two-operator-logins")
LOCK = Path("/run/lock/empire-bsc-two-operator-logins.lock")
ROOT = Path(__file__).resolve().parents[1]
SOCKET = "/var/run/postgresql"
NAMES = tuple(EXPECTED.values())


def safe_password_pair() -> dict[str, str]:
    """Separate cryptographically random SQL passwords, never logged."""
    values={name:secrets.token_urlsafe(48) for name in NAMES}
    if len(set(values.values())) != 2 or any(len(value) < 48 for value in values.values()):
        raise RuntimeError("financial operator secrets unavailable")
    return values


def _postgres_child(operation: str, payload: dict | None = None) -> dict:
    result=subprocess.run(
        ["runuser","-u","postgres","--",sys.executable,
         "-m","scripts.provision_bsc_financial_operator_logins",operation],
        input=None if payload is None else json.dumps(payload,sort_keys=True),
        capture_output=True,text=True,timeout=35,
        cwd=ROOT,
    )
    if result.returncode:
        raise RuntimeError("privileged operator transaction/canonical catalog unavailable")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _db():
    import psycopg
    return psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5"
    )


def _internal_catalog() -> dict:
    from empire_os.bsc_payment_operator_readiness import inspect_catalog
    return inspect_catalog(_db, vault_exists=False)


def _internal_apply(payload: dict) -> None:
    """One single PostgreSQL transaction; verifiers never appear in output."""
    import psycopg
    from psycopg import sql
    values=payload.get("verifiers")
    if (not isinstance(values,dict) or set(values)!=set(NAMES)
            or any(not isinstance(v,str) or not v.startswith("SCRAM-SHA-256$4096:")
                   or len(v)>220 for v in values.values())):
        raise RuntimeError("SCRAM verifier payload invalid")
    if _internal_catalog()["status"] != "READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING":
        raise RuntimeError("financial database preflight drift")
    with _db() as conn,conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='12000ms'")
        cur.execute("SET LOCAL lock_timeout='3000ms'")
        cur.execute("SET LOCAL password_encryption='scram-sha-256'")
        for group,login in EXPECTED.items():
            cur.execute(sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(login),sql.Literal(values[login])))
            cur.execute(sql.SQL(
                "GRANT {} TO {} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
            ).format(sql.Identifier(group),sql.Identifier(login)))
        # Every statement above commits atomically on context exit.
    # No caller-supplied SQL or discretionary grants.


def _internal_postcheck() -> dict:
    from empire_os.bsc_payment_operator_readiness import inspect_catalog
    return inspect_catalog(_db, vault_exists=True)


def _source_guard() -> None:
    filename="scripts/provision_bsc_financial_operator_logins.py"
    def git(*args: str) -> str:
        return subprocess.run(
            ["git","-c",f"safe.directory={ROOT}","-C",str(ROOT),*args],
            capture_output=True,text=True,check=True,timeout=6
        ).stdout.strip()
    try:
        if git("status","--porcelain","--",filename):
            raise RuntimeError("financial role deployment script changed")
        if git("hash-object",str(ROOT/filename))!=git("rev-parse","HEAD:"+filename):
            raise RuntimeError("financial role release not reviewed")
    except Exception as exc:
        raise RuntimeError("unreviewed operator login release source") from None


def _backup_global_roles() -> Path:
    BACKUPS.mkdir(parents=True,mode=0o700,exist_ok=True)
    if BACKUPS.is_symlink():
        raise RuntimeError("global role backup symlink")
    target=BACKUPS/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target.mkdir(mode=0o700)
    destination=target/"globals-before.sql"
    fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as out:
        result=subprocess.run(
            ["runuser","-u","postgres","--","pg_dumpall","-w","--globals-only"],
            stdout=out,stderr=subprocess.DEVNULL,timeout=75,
        )
        out.flush();os.fsync(out.fileno())
    if result.returncode or destination.stat().st_size<50:
        raise RuntimeError("privileged role backup unavailable")
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    evidence=target/"SHA256"
    evidence.write_text(digest+"  globals-before.sql\n")
    os.chmod(evidence,0o600)
    assert hashlib.sha256(destination.read_bytes()).hexdigest()==digest
    return target


def _store_credentials(passwords: dict[str,str]) -> None:
    if VAULT.exists() or VAULT.is_symlink():
        raise RuntimeError("existing operator credential vault not overwritten")
    VAULT.mkdir(mode=0o700)
    try:
        for login in NAMES:
            # Two completely distinct root-only password files, not in repo,
            # process argv, service env, HTTP, startup logs or public checkout.
            secret = f"{SOCKET}:5432:{DB}:{login}:{passwords[login]}\n"
            destination=VAULT/(login+".pgpass")
            fd=os.open(destination,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"w") as file:
                file.write(secret);file.flush();os.fsync(file.fileno())
        assert all((VAULT/(login+".pgpass")).stat().st_mode & 0o777==0o600 for login in NAMES)
    except Exception:
        shutil.rmtree(VAULT)
        raise


def _test_only_actual_login_auth(passwords: dict[str,str]) -> None:
    import psycopg
    from psycopg import sql
    for group,login in EXPECTED.items():
        with psycopg.connect(
            host=SOCKET,port=5432,dbname=DB,user=login,password=passwords[login],
            connect_timeout=5,application_name="empire-bsc-financial-operator-auth-readonly"
        ) as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='4000ms'")
            cur.execute("SELECT session_user,current_user,current_database()")
            assert cur.fetchone()==(login,login,DB)
            cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(group)))
            cur.execute("SELECT session_user,current_user")
            assert cur.fetchone()==(login,group)
            conn.rollback()


def _root_main(flags: list[str]) -> int:
    approved=flags==["--apply","--approved-two-bsc-financial-operator-logins"]
    if flags not in (
        ["--preflight"],["--apply","--approved-two-bsc-financial-operator-logins"]
    ):
        print("BSC_OPERATOR_LOGIN_STATUS=BLOCKED_EXACT_FOUNDER_APPROVAL_FLAGS")
        return 3
    if os.geteuid()!=0:
        print("BSC_OPERATOR_LOGIN_STATUS=BLOCKED_ROOT_REQUIRED")
        return 3
    try:
        with LOCK.open("a+") as locked:
            fcntl.flock(locked.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            hba_operator.prior.cluster_guard()
            report=_postgres_child("--internal-catalog")
            if VAULT.exists() or VAULT.is_symlink():
                report["status"]="BLOCKED_OPERATOR_VAULT_ALREADY_EXISTS"
            print(json.dumps(report,sort_keys=True))
            if report["status"] != "READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING":
                print("BSC_OPERATOR_LOGIN_STATUS=HELD_CATALOG_OR_HBA_UNREADY")
                return 2
            if not approved:
                print("BSC_OPERATOR_LOGIN_STATUS=READY_FOR_SEPARATE_EXACT_FOUNDER_APPROVAL")
                return 0
            _source_guard()
            # Persist backup and independent root-only secrets BEFORE catalog
            # mutation. SQL changes are atomic and may fail closed.
            backup=_backup_global_roles()
            print("BSC_OPERATOR_LOGIN_BACKUP_SHA256=VERIFIED")
            print("BSC_OPERATOR_LOGIN_BACKUP_PATH="+str(backup))
            passwords=safe_password_pair()
            _store_credentials(passwords)
            try:
                derived={role:scram_verifier(secret) for role,secret in passwords.items()}
                _postgres_child("--internal-apply",{"verifiers":derived})
            except Exception:
                # If no roles were committed, the vault may be rolled back.
                if _postgres_child("--internal-catalog")["status"]==(
                        "READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING"):
                    shutil.rmtree(VAULT)
                    print("BSC_OPERATOR_LOGIN_NO_DB_WRITES_VAULT_ROLLBACK=YES")
                raise
            post=_postgres_child("--internal-postcheck")
            if post["status"]!="OPERATOR_IDENTITIES_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED":
                raise RuntimeError("postcommit catalog safety proof failed")
            _test_only_actual_login_auth(passwords)
            print("BSC_OPERATOR_LOGIN_SQL_AUTHENTICATION_AND_SET_ROLE=VERIFIED_TWO_IDENTITIES")
            print("BSC_OPERATOR_LOGIN_FINANCIAL_ROLE_FUNCTIONS_EXECUTED=NO")
            print("BSC_OPERATOR_LOGIN_CHECKOUT_OR_FUND_TRANSFER_ACTIVATED=NO")
            print("BSC_OPERATOR_LOGIN_HUMAN_OPERATOR_ASSIGNMENTS=STILL_GATED")
            print("BSC_OPERATOR_LOGIN_STATUS=EXACT_TWO_SQL_IDENTITIES_PROVISIONED")
            return 0
    except Exception:
        print("BSC_OPERATOR_LOGIN_STATUS=HELD_NO_BLIND_RETRY_REQUIRE_RECONCILIATION")
        return 4


def main() -> int:
    flags=sys.argv[1:]
    if flags in (["--internal-catalog"],["--internal-apply"],["--internal-postcheck"]):
        import pwd
        if os.geteuid()!=pwd.getpwnam("postgres").pw_uid:
            return 3
        try:
            if flags==["--internal-catalog"]:
                print(json.dumps(_internal_catalog(),sort_keys=True))
            elif flags==["--internal-postcheck"]:
                print(json.dumps(_internal_postcheck(),sort_keys=True))
            else:
                _internal_apply(json.load(sys.stdin))
            return 0
        except Exception:
            return 4
    return _root_main(flags)


if __name__=="__main__":
    raise SystemExit(main())
