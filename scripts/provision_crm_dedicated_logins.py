#!/usr/bin/env python3
"""Founder-approved one-shot CRM dedicated DB LOGIN provisioning.

Intentionally refuses all writes unless dedicated local SCRAM HBA authentication
is ALREADY configured. This script NEVER changes pg_hba.conf, live services,
HTTP exposure, founder membership, outbound, or payment permissions.

Run --preflight as root first; run --apply --approved-three-crm-logins ONLY
if the preflight reports READY. No credentials ever enter argv or logs.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess
import sys
from uuid import UUID

TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"
SUBJECT = "founder:phil_livesley"
READER = "empire_crm_tenant_" + TENANT.replace("-", "")[:12]
AUTH = "empire_crm_auth_login"
MEMBER = "empire_crm_membership_login"
ROLES = (AUTH, MEMBER, READER)
HBA_AUTH = "scram-sha-256"
VAULT_DIR = Path("/var/lib/empire-crm-first-party")
PASSFILE = VAULT_DIR / "pgpass"
DB = "empiredb"
SOCKET = "/var/run/postgresql"


def hba_ready(rows: list[dict], roles: tuple[str, ...] = ROLES) -> bool:
    """Reject unsafe/shadowed HBA rules; accept exact role-only local SCRAM."""
    if not isinstance(rows, list) or any(not isinstance(x, dict) or x.get("error") for x in rows):
        return False
    ordered = sorted(rows, key=lambda r: (r.get("rule_number") if r.get("rule_number") is not None else r.get("line_number", 999999)))
    for target in roles:
        found = False
        for row in ordered:
            if row.get("type") != "local":
                continue
            dbs = row.get("database") or []
            users = row.get("user_name") or []
            if not isinstance(dbs, list) or not isinstance(users, list):
                return False
            # Conservatively treat role-group patterns as potential shadow.
            db_match = DB in dbs or "all" in dbs or "sameuser" in dbs
            user_match = target in users or "all" in users or any(
                isinstance(u, str) and u.startswith("+") for u in users
            )
            if not db_match or not user_match:
                continue
            if (users == [target] and dbs == [DB]
                    and row.get("auth_method") == HBA_AUTH):
                found = True
            break  # First matching rule is authoritative.
        if not found:
            return False
    return True


def _conn():
    import psycopg
    return psycopg.connect("host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5")


def catalog(*, vault_reserved: bool = False) -> dict:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5000ms'")
        cur.execute("SELECT current_database(),pg_is_in_recovery()")
        correct, recovery = cur.fetchone()
        cur.execute("SELECT rule_number,line_number,type,database,user_name,auth_method,error FROM pg_catalog.pg_hba_file_rules")
        keys = ("rule_number","line_number","type","database","user_name","auth_method","error")
        hba = [dict(zip(keys, row)) for row in cur.fetchall()]
        cur.execute(
            "SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_catalog.pg_roles WHERE rolname IN (%s,%s,%s,'empire_revenue_crm_reader')",
            ROLES,
        )
        roles = {r[0]: r[1:] for r in cur.fetchall()}
        no_login = all(
            roles.get(name) == (False, False, False, False, False, False, False)
            for name in (AUTH, MEMBER)
        )
        reader_group_safe = roles.get("empire_revenue_crm_reader") == (
            False, False, False, False, False, False, False
        )
        cur.execute("SELECT COUNT(*) FROM public.empire_crm_tenant_memberships "
                    "WHERE tenant_id=%s::uuid AND subject=%s AND role='owner' "
                    "AND status='active' AND revoked_at IS NULL "
                    "AND verified_at <= clock_timestamp() "
                    "AND (valid_until IS NULL OR valid_until > clock_timestamp()) "
                    "AND NULLIF(BTRIM(evidence_ref),'') IS NOT NULL",
                    (TENANT, SUBJECT))
        founder_one = cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM public.empire_crm_tenant_memberships "
                    "WHERE subject=%s", (SUBJECT,))
        no_duplicate_member = cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM public.empire_crm_login_credentials "
                    "WHERE subject=%s OR invitation_tenant_id=%s::uuid",
                    (SUBJECT, TENANT))
        credentials_empty = cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM public.empire_tenant_role_bindings "
                    "WHERE role_name=%s", (READER,))
        binding_empty = cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM pg_catalog.pg_auth_members am "
            "JOIN pg_catalog.pg_roles member ON member.oid=am.member "
            "WHERE member.rolname IN (%s,%s)",
            (AUTH, MEMBER),
        )
        identity_roles_uninherited = cur.fetchone()[0] == 0
        cur.execute(
            "SELECT to_regprocedure('public.empire_current_tenant_id()') IS NOT NULL,"
            "to_regclass('public.revenue_crm_prospects') IS NOT NULL,"
            "to_regclass('public.revenue_crm_buyers') IS NOT NULL"
        )
        tenant_fn, prospect_view, buyer_view = cur.fetchone()
    ready = bool(
        correct == DB and not recovery and no_login and reader_group_safe
        and READER not in roles and founder_one and no_duplicate_member
        and credentials_empty and binding_empty and identity_roles_uninherited
        and tenant_fn and prospect_view and buyer_view and hba_ready(hba)
        and (vault_reserved or not VAULT_DIR.exists())
    )
    return {
        "schema": "empire.crm.dedicated_logins_preflight.v1",
        "mode": "OBSERVE", "production_write_performed": False,
        "canonical_database": correct == DB and not recovery,
        "founder_active_single_owner": founder_one and no_duplicate_member,
        "founder_credential_rows_zero": credentials_empty,
        "auth_and_membership_roles_safe_nologin": no_login and identity_roles_uninherited,
        "crm_reader_group_safe": reader_group_safe,
        "tenant_reader_role_and_binding_absent": READER not in roles and binding_empty,
        "canonical_tenant_views_and_function_present": bool(tenant_fn and prospect_view and buyer_view),
        "local_exact_role_scram_auth_ready": hba_ready(hba),
        "private_credential_vault_unused": not VAULT_DIR.exists(),
        "status": "READY_TO_PROVISION" if ready else "BLOCKED_NO_CHANGES",
    }


def scram_verifier(password: str, salt: bytes | None = None) -> str:
    """PostgreSQL SCRAM verifier: only irreversible derived values enter DDL."""
    if not isinstance(password, str) or len(password) < 32:
        raise ValueError("random SCRAM password required")
    raw_salt = secrets.token_bytes(16) if salt is None else salt
    if not isinstance(raw_salt, bytes) or len(raw_salt) != 16:
        raise ValueError("SCRAM salt invalid")
    rounds = 4096
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), raw_salt, rounds)
    stored_key = hashlib.sha256(hmac.new(salted, b"Client Key", hashlib.sha256).digest()).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda blob: base64.b64encode(blob).decode("ascii")
    return f"SCRAM-SHA-256${rounds}:{b64(raw_salt)}${b64(stored_key)}:{b64(server_key)}"


def operator_apply(data: dict) -> None:
    """Run only as postgres under the root orchestrator, on canonical socket."""
    import psycopg
    from psycopg import sql
    verifiers = data.get("verifiers")
    if (not isinstance(verifiers, dict) or set(verifiers) != set(ROLES)
        or any(not isinstance(value, str)
               or not value.startswith("SCRAM-SHA-256$4096:")
               or len(value) > 220 for value in verifiers.values())):
        raise RuntimeError("invalid secret handoff")
    with _conn() as conn, conn.cursor() as cur:
        if catalog(vault_reserved=True)["status"] != "READY_TO_PROVISION":
            raise RuntimeError("catalog changed before transaction")
        cur.execute("SET LOCAL statement_timeout='12000ms'")
        cur.execute("SET LOCAL lock_timeout='3000ms'")
        cur.execute("SET LOCAL password_encryption='scram-sha-256'")
        for role in (AUTH, MEMBER):
            cur.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(verifiers[role])
                )
            )
        cur.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(
                        sql.Identifier(READER), sql.Literal(verifiers[READER])
                    )
        )
        cur.execute(
            sql.SQL("GRANT empire_revenue_crm_reader TO {} WITH INHERIT FALSE, SET TRUE").format(
                sql.Identifier(READER)
            )
        )
        cur.execute(
            "INSERT INTO public.empire_tenant_role_bindings "
            "(role_name,tenant_id,active,evidence_ref) VALUES (%s,%s::uuid,true,%s)",
            (READER, TENANT, "founder:approved-three-dedicated-crm-logins-20261010"),
        )
    # No credential print or SQL text log.




def postcommit_catalog() -> dict:
    """Read-only catalog proof. Never returns role password verifiers."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5000ms'")
        cur.execute(
            "SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,"
            "rolcreaterole,rolreplication,rolbypassrls,"
            "coalesce(rolpassword LIKE 'SCRAM-SHA-256$%%',false) "
            "FROM pg_catalog.pg_authid WHERE rolname IN (%s,%s,%s)",
            ROLES,
        )
        identities = {row[0]:row[1:] for row in cur.fetchall()}
        cur.execute(
            "SELECT group_role.rolname FROM pg_catalog.pg_auth_members am "
            "JOIN pg_catalog.pg_roles group_role ON am.roleid=group_role.oid "
            "JOIN pg_catalog.pg_roles member ON am.member=member.oid "
            "WHERE member.rolname=%s", (READER,),
        )
        membership = [row[0] for row in cur.fetchall()]
        cur.execute(
            "SELECT COUNT(*) FROM public.empire_tenant_role_bindings "
            "WHERE role_name=%s AND tenant_id=%s::uuid AND active "
            "AND NULLIF(BTRIM(evidence_ref),'') IS NOT NULL", (READER,TENANT),
        )
        canonical_binding = cur.fetchone()[0] == 1
        cur.execute(
            "SELECT COUNT(*) FROM public.empire_crm_login_credentials "
            "WHERE subject=%s OR invitation_tenant_id=%s::uuid", (SUBJECT,TENANT),
        )
        account_credentials_unchanged = cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM pg_catalog.pg_auth_members am "
            "JOIN pg_catalog.pg_roles r ON am.member=r.oid "
            "WHERE r.rolname IN (%s,%s)", (AUTH,MEMBER),
        )
        no_identity_memberships = cur.fetchone()[0] == 0
    safe_attrs = (True,False,False,False,False,False,False,True)
    ready = (
        all(identities.get(role)==safe_attrs for role in ROLES)
        and membership == ["empire_revenue_crm_reader"]
        and canonical_binding and account_credentials_unchanged
        and no_identity_memberships
    )
    return {
        "schema":"empire.crm.three_dedicated_login_catalog_readback.v1",
        "three_safe_scram_login_roles":all(identities.get(role)==safe_attrs for role in ROLES),
        "reader_group_only":membership == ["empire_revenue_crm_reader"],
        "one_evidenced_tenant_binding":canonical_binding,
        "founder_account_credential_rows_unchanged":account_credentials_unchanged,
        "auth_and_membership_extra_memberships":not no_identity_memberships,
        "status":"CATALOG_VERIFIED" if ready else "CATALOG_UNVERIFIED",
    }


def run_as_postgres(mode: str, private_payload: dict | None = None):
    command = ["runuser", "-u", "postgres", "--",
               sys.executable, str(Path(__file__).resolve()), mode]
    result = subprocess.run(
        command,
        input=None if private_payload is None else json.dumps(private_payload),
        text=True, capture_output=True, timeout=35,
    )
    if result.returncode != 0:
        raise RuntimeError("privileged CRM catalog or role transaction unavailable")
    return result.stdout




def reviewed_release_guard() -> None:
    """Before apply, verify exact checked-in source (not a temporary edit)."""
    relative = "scripts/provision_crm_dedicated_logins.py"
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-c", f"safe.directory={Path(__file__).resolve().parents[1]}",
             "-C", str(Path(__file__).resolve().parents[1]), *args],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return proc.stdout.strip()
    try:
        if git("status","--porcelain","--",relative):
            raise RuntimeError("pending login operator changes")
        if git("hash-object",str(Path(__file__).resolve())) != git("rev-parse","HEAD:"+relative):
            raise RuntimeError("CRM login operator source mismatch")
    except Exception:
        raise RuntimeError("unreviewed CRM login operator") from None


def backup_catalog() -> Path:
    """Save restricted global-roles and tenant-binding table recovery material."""
    import datetime
    base = Path("/var/backups/empiredb/crm-founder-three-dedicated-logins")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    if base.is_symlink():
        raise RuntimeError("backup directory must not be a symlink")
    folder = base / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(mode=0o700)
    for filename, args in (
        ("roles-before.sql", ["pg_dumpall","-w","--globals-only"]),
        ("bindings-before.dump",
         ["pg_dump","-w","-Fc","-d",DB,"-t","public.empire_tenant_role_bindings"]),
    ):
        target = folder / filename
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as target_file:
            result = subprocess.run(
                ["runuser","-u","postgres","--",*args],
                stdout=target_file, stderr=subprocess.DEVNULL, timeout=90,
            )
        if result.returncode or not target.stat().st_size:
            raise RuntimeError("restricted CRM backup failed")
    checked = subprocess.run(
        ["pg_restore","--list",str(folder/"bindings-before.dump")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
    )
    if checked.returncode:
        raise RuntimeError("CRM binding archive invalid")
    report = []
    for filename in ("roles-before.sql","bindings-before.dump"):
        report.append(hashlib.sha256((folder/filename).read_bytes()).hexdigest()+"  "+filename)
    manifest = folder / "SHA256SUMS"
    fd = os.open(manifest,os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w",encoding="ascii") as output:
        output.write("\n".join(report)+"\n")
    for name,digest in zip(("roles-before.sql","bindings-before.dump"),
                           [x.split()[0] for x in report],strict=True):
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError("CRM backup SHA256 verification failed")
    return folder


def _write_passfile(passwords: dict[str, str]):
    if VAULT_DIR.exists() or VAULT_DIR.is_symlink():
        raise RuntimeError("credential vault already exists")
    account = pwd.getpwnam("ubuntu")
    VAULT_DIR.mkdir(mode=0o700)
    try:
        os.chown(VAULT_DIR, account.pw_uid, account.pw_gid)
        contents = "".join(
            f"{SOCKET}:5432:{DB}:{role}:{passwords[role]}\n"
            for role in ROLES
        )
        fd = os.open(PASSFILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(contents)
            file.flush()
            os.fsync(file.fileno())
        os.chown(PASSFILE, account.pw_uid, account.pw_gid)
    except Exception:
        raise RuntimeError("private credential file unavailable") from None


def _verify_logins():
    import subprocess
    for role in ROLES:
        command = [
            "runuser", "-u", "ubuntu", "--",
            "psql", "-X", "-w", "-q", "-At", "-v", "ON_ERROR_STOP=1",
            "-h", SOCKET, "-p", "5432", "-U", role, "-d", DB,
            "-c", "SELECT session_user",
        ]
        env = {**os.environ, "PGPASSFILE": str(PASSFILE)}
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=8)
        if result.returncode != 0 or result.stdout.strip() != role:
            raise RuntimeError("actual CRM role authentication test failed")
    # Prove the only new account's canonical DB session tenant identity.
    proof = subprocess.run([
        "runuser", "-u", "ubuntu", "--",
        "psql", "-X", "-w", "-q", "-At", "-v", "ON_ERROR_STOP=1",
        "-h", SOCKET, "-p", "5432", "-U", READER, "-d", DB,
        "-c", "BEGIN READ ONLY; SET LOCAL ROLE empire_revenue_crm_reader;"
              " SELECT public.empire_current_tenant_id(); ROLLBACK;",
    ], env={**os.environ, "PGPASSFILE": str(PASSFILE)},
       capture_output=True, text=True, timeout=8)
    if proof.returncode != 0 or proof.stdout.splitlines() != [TENANT]:
        raise RuntimeError("new CRM reader tenant binding unverified")


def main() -> int:
    argv = sys.argv[1:]
    internal = argv in (["--internal-catalog"], ["--internal-apply"], ["--internal-readback"])
    if internal:
        if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
            return 3
        try:
            if argv == ["--internal-catalog"]:
                print(json.dumps(catalog(), sort_keys=True))
            elif argv == ["--internal-readback"]:
                print(json.dumps(postcommit_catalog(), sort_keys=True))
            else:
                operator_apply(json.load(sys.stdin))
            return 0
        except Exception:
            return 4
    if os.geteuid() != 0:
        print("CRM_LOGIN_STATUS=BLOCKED_ROOT_OPERATOR_REQUIRED")
        return 3
    if argv not in (["--preflight"], ["--apply", "--approved-three-crm-logins"]):
        print("CRM_LOGIN_STATUS=BLOCKED_EXACT_APPROVAL_ARGUMENTS_REQUIRED")
        return 3
    try:
        report = json.loads(run_as_postgres("--internal-catalog"))
        if argv == ["--preflight"]:
            print(json.dumps(report, sort_keys=True))
            return 0 if report["status"] == "READY_TO_PROVISION" else 2
        if report["status"] != "READY_TO_PROVISION":
            print("CRM_LOGIN_STATUS=BLOCKED_PREFLIGHT_NO_CHANGES")
            return 2
        # Production role authority is single-writer and committed-source-only.
        lock_path = Path("/run/lock/empire-crm-three-logins.lock")
        with lock_path.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            checked = json.loads(run_as_postgres("--internal-catalog"))
            if checked["status"] != "READY_TO_PROVISION":
                raise RuntimeError("live CRM prerequisites changed")
            reviewed_release_guard()
            backup_dir = backup_catalog()
            print("CRM_LOGIN_BACKUP=GLOBALS_AND_TENANT_BINDINGS_VERIFIED_SHA256")
            print("CRM_LOGIN_BACKUP_LOCATION="+str(backup_dir))
            # Secrets are generated on the server, never provided in argv.
            # Pre-create restricted passfile; any failed DB transaction requires
            # manual reconciliation of this unused file, NOT a blind retry.
            passwords = {role: secrets.token_urlsafe(36) for role in ROLES}
            verifiers = {role: scram_verifier(passwords[role]) for role in ROLES}
            _write_passfile(passwords)
            print("CRM_LOGIN_PRIVATE_CREDENTIAL_FILE=CREATED_SERVER_ONLY")
            run_as_postgres("--internal-apply", {"verifiers": verifiers})
            print("CRM_LOGIN_ROLE_TRANSACTION=COMMITTED")
            _verify_logins()
            print("CRM_LOGIN_SESSION_AUTH_AND_FOUNDER_TENANT_PROOF=PASS")
        print("CRM_LOGIN_FOUNDERS_CREDENTIAL_ROW_CREATED=NO")
        print("CRM_LOGIN_HTTP_OUTBOUND_PAYMENT_ACTIVATION=NO")
        print("CRM_LOGIN_STATUS=THREE_DEDICATED_LOGINS_VERIFIED")
        return 0
    except Exception:
        # Never leak DSN, generated passwords, tenant ID, DB records or stack.
        print("CRM_LOGIN_STATUS=BLOCKED_OR_UNVERIFIED_DO_NOT_BLINDLY_RETRY")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
