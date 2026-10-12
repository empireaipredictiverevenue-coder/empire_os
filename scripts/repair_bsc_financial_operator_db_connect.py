#!/usr/bin/env python3
"""Repair EXACT TWO missing CONNECT grants on canonical EmpireDB financial logins.

A one-shot, fail-closed repair for logins already safely provisioned with two
separate SCRAM authentication rules and exact NOINHERIT financial memberships.

Default --preflight is READ ONLY. Actual SQL GRANT requires the exact approval
--apply --approved-exact-two-bsc-db-connect-grants; no payment approval,
escrow evidence mutation, mainnet signing, new role, password/HBA mutation,
public checkout change, contract deployment or funds movement is performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from empire_os.bsc_payment_operator_readiness import (
    DB, EXPECTED, LOGIN_ROLES,
)
from scripts import provision_bsc_financial_operator_logins as existing

ROOT = Path(__file__).resolve().parents[1]
LOCK = Path("/run/lock/empire-bsc-financial-db-connect-repair.lock")
BACKUP = Path("/var/backups/empiredb/bsc-two-operator-connect")
REQUIRES_GRANTS = "OPERATOR_IDENTITIES_REQUIRE_EXACT_TWO_DATABASE_CONNECT_GRANTS"
CATALOG_READY = "OPERATOR_IDENTITIES_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"
VAULT = existing.VAULT


def _postgres_child(operation: str) -> dict:
    if operation not in ("--internal-catalog", "--internal-apply", "--internal-db-acl"):
        raise RuntimeError("unsupported privileged operation")
    p=subprocess.run(
        ["runuser","-u","postgres","--",sys.executable,
         "-m","scripts.repair_bsc_financial_operator_db_connect",operation],
        cwd=ROOT,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH": str(ROOT),
            "HOME": "/var/lib/postgresql",
            "PGHOST": existing.SOCKET,
            "PGPORT": "5432",
            "PGDATABASE": DB,
        },
        capture_output=True,text=True,timeout=25,
    )
    if p.returncode:
        raise RuntimeError("financial database privileged check unavailable")
    return json.loads(p.stdout) if p.stdout.strip() else {}


def _read_catalog() -> dict:
    return existing._internal_catalog()


def _db_acl() -> dict:
    with existing._db() as conn,conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='3500ms'")
        cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
        assert cur.fetchone()==(DB,"postgres",False)
        cur.execute("""
            SELECT datacl::text,datallowconn
            FROM pg_catalog.pg_database WHERE datname=%s
        """,(DB,))
        acl=cur.fetchone()
        assert acl is not None and acl[1] is True
        rows=[]
        for login in LOGIN_ROLES:
            cur.execute("""SELECT has_database_privilege(%s,%s,'CONNECT'),
                has_database_privilege(%s,%s,'CREATE'),
                has_database_privilege(%s,%s,'TEMP')""",
                (login,DB,login,DB,login,DB))
            rows.append([login,*cur.fetchone()])
        conn.rollback()
    return {"database":DB,"raw_database_acl":acl[0],"role_database_privileges":rows}


def _internal_grant() -> dict:
    # A repeated or partially mutated run is blocked. Both exact already
    # provisioned logins must be missing only CONNECT, with zero CREATE/TEMP.
    catalog=_read_catalog()
    if catalog["status"]!=REQUIRES_GRANTS or catalog["operator_db_connect_grant_count"]!=0:
        raise RuntimeError("financial operator identity/privilege precondition drift")
    from psycopg import sql
    with existing._db() as conn,conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='6000ms'")
        cur.execute("SET LOCAL lock_timeout='2000ms'")
        for login in LOGIN_ROLES:
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(DB),sql.Identifier(login)))
        # Both exact CONNECT grants commit in the same SQL transaction.
    result=_read_catalog()
    if result["status"]!=CATALOG_READY or result["operator_db_connect_grant_count"]!=2:
        raise RuntimeError("postcommit connect grants require review")
    return {"status":"EXACT_TWO_DATABASE_CONNECT_GRANTS_COMMITTED",
            "granted_logins":2,"db_create_grants":0,"db_temporary_grants":0,
            "auth_tested":False,"payment_collection_enabled":False}


def _source_guard() -> None:
    name="scripts/repair_bsc_financial_operator_db_connect.py"
    def git(*args: str) -> str:
        return subprocess.run(
            ["git","-c",f"safe.directory={ROOT}","-C",str(ROOT),*args],
            capture_output=True,text=True,check=True,timeout=6,
        ).stdout.strip()
    try:
        if git("status","--porcelain","--",name):
            raise RuntimeError()
        if git("hash-object",str(ROOT/name))!=git("rev-parse","HEAD:"+name):
            raise RuntimeError()
    except Exception as exc:
        raise RuntimeError("unreviewed SQL privilege repair source") from None


def _ensure_vault_safe() -> bool:
    if (not VAULT.is_dir() or VAULT.is_symlink()
            or (VAULT.stat().st_mode & 0o777)!=0o700
            or VAULT.stat().st_uid!=0 or VAULT.stat().st_gid!=0):
        return False
    for login in LOGIN_ROLES:
        path=VAULT/(login+".pgpass")
        if (path.is_symlink() or not path.is_file()
                or (path.stat().st_mode & 0o777)!=0o600
                or path.stat().st_uid!=0 or path.stat().st_gid!=0):
            return False
    return True


def _backup_acl() -> Path:
    BACKUP.mkdir(parents=True,mode=0o700,exist_ok=True)
    if BACKUP.is_symlink():
        raise RuntimeError("backup path symlink")
    location=BACKUP/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    location.mkdir(mode=0o700)
    report=_postgres_child("--internal-db-acl")
    assert report["database"]==DB
    assert all(not row[1] and not row[2] and not row[3]
               for row in report["role_database_privileges"])
    payload=(json.dumps(report,sort_keys=True,indent=2)+"\n").encode()
    destination=location/"db-acl-before.json"
    fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(payload);out.flush();os.fsync(out.fileno())
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    assert digest==hashlib.sha256(payload).hexdigest()
    return location


def _verify_two_password_logins() -> None:
    # Secrets only read in-process from the canonical root-only passfiles.
    secrets={}
    for login in LOGIN_ROLES:
        value=(VAULT/(login+".pgpass")).read_text().rstrip("\n")
        host,port,dbname,user,password=value.split(":",4)
        if (host,port,dbname,user)!=(existing.SOCKET,"5432",DB,login) or len(password)<48:
            raise RuntimeError("invalid independent operator passfile")
        secrets[login]=password
    if len(set(secrets.values()))!=2:
        raise RuntimeError("operator passwords are not independent")
    existing._test_only_actual_login_auth(secrets)
    import psycopg
    from psycopg import sql
    for group,login in EXPECTED.items():
        other=next(item for item in EXPECTED if item!=group)
        try:
            with psycopg.connect(
                host=existing.SOCKET,port=5432,dbname=DB,user=login,
                password=secrets[login],connect_timeout=5,
                application_name="empire-bsc-operator-cross-role-denial"
            ) as conn,conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(other)))
            raise RuntimeError("unexpected cross-role SET access")
        except psycopg.errors.InsufficientPrivilege:
            pass


def _root_main(args: list[str]) -> int:
    allowed_preflight=args==["--preflight"]
    approved=args==["--apply","--approved-exact-two-bsc-db-connect-grants"]
    if not (allowed_preflight or approved):
        print("BSC_DB_CONNECT_STATUS=HELD_EXACT_APPROVAL_FLAG_REQUIRED")
        return 3
    if os.geteuid()!=0:
        print("BSC_DB_CONNECT_STATUS=HELD_ROOT_REQUIRED")
        return 3
    try:
        with LOCK.open("a+") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            existing.hba_operator.prior.cluster_guard()
            cat=_postgres_child("--internal-catalog")
            print(json.dumps({
                "catalog_status":cat["status"],
                "exact_db_connect_grants":cat.get("operator_db_connect_grant_count",0),
                "both_hba_rules_effective":cat["two_exact_local_scram_rules_effective"],
                "roles_and_memberships_safe":(
                    cat["exact_existing_nologin_permission_roles_safe"]
                    and cat["exact_noninherited_set_role_memberships"]
                ),
                "mode":"READ_ONLY" if not approved else "EXACT_CONNECT_GRANTS_ONLY",
                "checkout_payment_activation":False,
            },sort_keys=True))
            if not _ensure_vault_safe():
                print("BSC_DB_CONNECT_STATUS=HELD_OPERATOR_VAULT_UNVERIFIED")
                return 2
            if cat["status"]==CATALOG_READY:
                if approved:
                    print("BSC_DB_CONNECT_STATUS=ALREADY_GRANTED_NO_SQL_CHANGE")
                else:
                    print("BSC_DB_CONNECT_STATUS=ALREADY_GRANTED_AUTH_CHECK_PENDING")
                return 0
            if cat["status"]!=REQUIRES_GRANTS:
                print("BSC_DB_CONNECT_STATUS=HELD_UNSAFE_PARTIAL_OR_AUTHORITY_DRIFT")
                return 2
            if not approved:
                print("BSC_DB_CONNECT_STATUS=READY_FOR_EXACT_TWO_CONNECT_GRANT_APPROVAL")
                return 0
            _source_guard()
            backup=_backup_acl()
            print("BSC_DB_CONNECT_BACKUP_SHA256_VERIFIED=YES")
            print("BSC_DB_CONNECT_BACKUP_DIRECTORY="+str(backup))
            result=_postgres_child("--internal-apply")
            assert result["status"]=="EXACT_TWO_DATABASE_CONNECT_GRANTS_COMMITTED"
            readback=_postgres_child("--internal-catalog")
            if readback["status"]!=CATALOG_READY:
                raise RuntimeError("grant catalog safety readback held")
            _verify_two_password_logins()
            print("BSC_DB_CONNECT_INDEPENDENT_AUTH_AND_ROLE_ISOLATION=PASS")
            print("BSC_DB_CONNECT_OPERATOR_HUMAN_ASSIGNMENT=STILL_GATED")
            print("BSC_DB_CONNECT_CHECKOUT_PAYMENT_ACTIVATED=NO")
            print("BSC_DB_CONNECT_STATUS=EXACT_TWO_CONNECT_GRANTS_VERIFIED")
            return 0
    except Exception:
        print("BSC_DB_CONNECT_STATUS=HELD_NO_BLIND_RETRY_REQUIRES_RECONCILIATION")
        return 4


def main() -> int:
    args=sys.argv[1:]
    if args in (["--internal-catalog"],["--internal-db-acl"],["--internal-apply"]):
        import pwd
        if os.geteuid()!=pwd.getpwnam("postgres").pw_uid:
            return 3
        try:
            if args==["--internal-catalog"]:
                print(json.dumps(_read_catalog(),sort_keys=True))
            elif args==["--internal-db-acl"]:
                print(json.dumps(_db_acl(),sort_keys=True))
            else:
                print(json.dumps(_internal_grant(),sort_keys=True))
            return 0
        except Exception:
            return 4
    return _root_main(args)


if __name__=="__main__":
    raise SystemExit(main())
