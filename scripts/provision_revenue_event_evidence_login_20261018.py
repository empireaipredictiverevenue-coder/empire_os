#!/usr/bin/env python3
"""One-founder-approved, one-tenant EmpireDB revenue evidence LOGIN release.

--preflight is read-only; --apply-approved-one-tenant-login is root-local.
Never creates an event, calls a payment API, exports source tables or sends mail.
No password, verifier, raw HBA, customer record or tenant member is printed.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from uuid import UUID

from empire_os.rev051_pgbackrest_readiness import review_pgbackrest_info
from scripts.provision_crm_dedicated_logins import scram_verifier

ROOT = Path("/srv/empire_os")
SCRIPT = "scripts/provision_revenue_event_evidence_login_20261018.py"
LOGIN = "empire_predictive_revenue_evidence_login"
ROLE = "empire_predictive_revenue_evidence_reader"
TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"
SUBJECT = "founder:phil_livesley"
HBA = Path("/etc/postgresql/18/main/pg_hba.conf")
VAULT = Path("/etc/empire/revenue-event-evidence")
PASSFILE = VAULT / "reader.pgpass"
LOCK = Path("/run/lock/empire-revenue-evidence-single-login.lock")
RECOVERY = Path("/var/backups/empiredb/rev052-one-reader-hba")
DB = "empiredb"
PREFIX = (
    "# BEGIN EMPIRE_REV052_ONE_EVENT_EVIDENCE_LOGIN\n"
    "local empiredb empire_predictive_revenue_evidence_login scram-sha-256\n"
    "# END EMPIRE_REV052_ONE_EVENT_EVIDENCE_LOGIN\n"
)


def pg(sql: str) -> str:
    """Local trusted postgres peer only; SQL via stdin, never argv or logs."""
    completed = subprocess.run(
        ["/usr/sbin/runuser","-u","postgres","--","/usr/bin/psql",
         "-X","-q","-w","-A","-t",
         "-v","ON_ERROR_STOP=1","-h","/var/run/postgresql","-p","5432",
         "-U","postgres","-d",DB],
        input=sql,capture_output=True,text=True,timeout=18,
        env={"PATH":"/usr/bin:/bin","HOME":"/var/lib/postgresql"},
    )
    if completed.returncode:
        raise RuntimeError("EMPIREDB_SQL_PRECHECK_OR_TRANSACTION_FAILED")
    return completed.stdout.strip()


def readiness_sql() -> str:
    return f"""BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT pg_catalog.jsonb_build_object(
 'canonical',current_database()='empiredb' AND NOT pg_catalog.pg_is_in_recovery(),
 'postgres18',current_setting('server_version_num')::int>=180000,
 'tenant_resolver',
   pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NOT NULL,
 'reader_capability',
   EXISTS(SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='{ROLE}' AND NOT rolcanlogin AND NOT rolsuper
       AND NOT rolinherit AND NOT rolbypassrls
       AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication),
 'reader_function',
   EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
     WHERE p.oid=pg_catalog.to_regprocedure(
       'public.read_predictive_revenue_event_v1(uuid,text)')
       AND p.prosecdef AND p.provolatile='s'
       AND (p.proconfig=ARRAY['search_path=']::text[]
           OR p.proconfig=ARRAY['search_path=""']::text[])
       AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                       WHERE rolname='empiredb_migrator')),
 'login_absent',NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}'),
 'capability_unassigned',
   NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members
     WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='{ROLE}')),
 'tenant_bind_absent',
   NOT EXISTS(SELECT 1 FROM public.empire_tenant_role_bindings
     WHERE role_name='{LOGIN}'),
 'one_active_founder_owner',
   (SELECT count(*)=1 FROM public.empire_crm_tenant_memberships
      WHERE tenant_id='{TENANT}'::uuid AND subject='{SUBJECT}'
        AND role='owner' AND status='active' AND revoked_at IS NULL
        AND verified_at IS NOT NULL
        AND (valid_until IS NULL OR valid_until>clock_timestamp())),
 'known_existing_tenant',
   (SELECT count(*)>=1 FROM public.empire_tenant_role_bindings
      WHERE tenant_id='{TENANT}'::uuid AND active
        AND nullif(btrim(evidence_ref),'') IS NOT NULL),
 'financial_tables_exist',
   pg_catalog.to_regclass('public.commercial_events') IS NOT NULL
   AND pg_catalog.to_regclass('public.fulfilment_orders') IS NOT NULL
   AND pg_catalog.to_regclass('public.buyers') IS NOT NULL,
 'capability_table_read_denied',
   NOT EXISTS (
      SELECT 1 FROM (VALUES ('public.commercial_events'),
                            ('public.fulfilment_orders'),
                            ('public.buyers')) s(n)
      WHERE pg_catalog.has_table_privilege('{ROLE}',s.n,'SELECT')),
 'hba_valid',NOT EXISTS(
      SELECT 1 FROM pg_catalog.pg_hba_file_rules WHERE error IS NOT NULL),
 'hba_file_matches',current_setting('hba_file')=
      '/etc/postgresql/18/main/pg_hba.conf',
 'data_directory_matches',current_setting('data_directory')=
      '/var/lib/postgresql/18/main'
)::text;
ROLLBACK;"""


def catalog() -> dict:
    lines = pg(readiness_sql()).splitlines()
    if len(lines)!=1:
        raise RuntimeError("BAD_READ_ONLY_CATALOG_SHAPE")
    data=json.loads(lines[0])
    if not isinstance(data,dict):
        raise RuntimeError("BAD_READ_ONLY_CATALOG_TYPE")
    return data


def reviewed_script() -> bool:
    # File must exactly equal the current Git HEAD, even with other agents'
    # unrelated dirty files. Fail closed on altered/uncommitted release source.
    try:
        a=subprocess.run(
            ["git","-c",f"safe.directory={ROOT}","-C",str(ROOT),
             "rev-parse",f"HEAD:{SCRIPT}"],
            capture_output=True,text=True,timeout=5,check=True)
        b=subprocess.run(["git","hash-object",str(ROOT/SCRIPT)],
                         capture_output=True,text=True,timeout=5,check=True)
        c=subprocess.run(
            ["git","-c",f"safe.directory={ROOT}","-C",str(ROOT),
             "status","--porcelain","--",SCRIPT],
            capture_output=True,text=True,timeout=5,check=True)
        return (bool(a.stdout.strip()) and a.stdout.strip()==b.stdout.strip()
                and not c.stdout.strip())
    except (OSError,subprocess.SubprocessError):
        return False


def backup_ready() -> bool:
    output=subprocess.run(
        ["runuser","-u","postgres","--","pgbackrest",
         "--config=/etc/pgbackrest/empiredb.conf",
         "--stanza=empiredb","--output=json","info"],
        capture_output=True,timeout=25,check=False,
    )
    if output.returncode or len(output.stdout)>2_000_000:
        return False
    summary=review_pgbackrest_info(json.loads(output.stdout))
    return summary.get("status")=="PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"


def strict_hba() -> tuple[os.stat_result,bytes]:
    if HBA.is_symlink() or not HBA.is_file():
        raise RuntimeError("HBA_PATH_UNEXPECTED")
    st=HBA.stat()
    if (st.st_uid != pwd.getpwnam("postgres").pw_uid
         or not stat.S_ISREG(st.st_mode)
         or (stat.S_IMODE(st.st_mode)&0o027)):
        raise RuntimeError("HBA_OWNER_PERMISSIONS_DRIFT")
    original=HBA.read_bytes()
    if (not original.strip() or b"\x00" in original
        or b"\r" in original or b"EMPIRE_REV052_ONE_EVENT_EVIDENCE_LOGIN" in original):
        raise RuntimeError("HBA_ALREADY_EDITED_OR_MALFORMED")
    return st,original


def write_hba(blob: bytes, metadata: os.stat_result) -> None:
    fd,path=tempfile.mkstemp(prefix=".rev052-hba-",dir=HBA.parent)
    try:
        with os.fdopen(fd,"wb") as file:
            file.write(blob)
            file.flush()
            os.fsync(file.fileno())
        os.chown(path,metadata.st_uid,metadata.st_gid)
        os.chmod(path,stat.S_IMODE(metadata.st_mode))
        os.replace(path,HBA)
    finally:
        if os.path.lexists(path):
            os.unlink(path)


def save_hba_backup(original: bytes) -> None:
    RECOVERY.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(RECOVERY,0o700)
    filename=RECOVERY/("pg_hba.before."+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    with filename.open("xb") as handle:
        os.fchmod(handle.fileno(),0o600)
        handle.write(original)
        handle.flush()
        os.fsync(handle.fileno())
    if filename.read_bytes()!=original:
        raise RuntimeError("HBA_BACKUP_MISMATCH")


def active_hba_reload() -> None:
    if pg("SELECT pg_catalog.pg_reload_conf();").strip()!="t":
        raise RuntimeError("HBA_RELOAD_REJECTED")


def provision_sql(scram: str) -> str:
    if not isinstance(scram,str) or not scram.startswith("SCRAM-SHA-256$4096:"):
        raise ValueError("INVALID_SCRAM_VERIFIER")
    # Only derived verifier, never plaintext password, is transmitted to
    # the privileged local postgres peer through stdin (no SQL log output).
    return f"""BEGIN;
SET LOCAL statement_timeout='12000ms';
SET LOCAL lock_timeout='3000ms';
DO $guard$
BEGIN
 IF current_database()<>'empiredb'
    OR pg_catalog.pg_is_in_recovery()
    OR pg_catalog.to_regrole('{LOGIN}') IS NOT NULL
    OR pg_catalog.to_regrole('{ROLE}') IS NULL
    OR NOT EXISTS(
       SELECT 1 FROM public.empire_crm_tenant_memberships
       WHERE tenant_id='{TENANT}'::uuid AND subject='{SUBJECT}'
         AND role='owner' AND status='active' AND revoked_at IS NULL)
    OR EXISTS(
       SELECT 1 FROM public.empire_tenant_role_bindings
       WHERE role_name='{LOGIN}')
    OR EXISTS(
       SELECT 1 FROM pg_catalog.pg_auth_members
       WHERE roleid=pg_catalog.to_regrole('{ROLE}'))
 THEN RAISE EXCEPTION 'REV052_SOURCE_PREREQUISITES_CHANGED'; END IF;
END;
$guard$;
CREATE ROLE {LOGIN} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS PASSWORD '{scram}';
ALTER ROLE {LOGIN} SET statement_timeout='4000ms';
GRANT CONNECT ON DATABASE empiredb TO {LOGIN};
GRANT {ROLE} TO {LOGIN} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
INSERT INTO public.empire_tenant_role_bindings(
  role_name,tenant_id,active,evidence_ref)
VALUES ('{LOGIN}','{TENANT}'::uuid,true,
        'founder:approved-one-revenue-evidence-login-20261018');
COMMIT;"""


def archive_matches_active_repository() -> bool:
    observed=pg("SELECT (current_setting('archive_mode')='on' "
                "AND current_setting('archive_command')="
                "'/usr/bin/pgbackrest --config=/etc/pgbackrest/empiredb.conf "
                "--stanza=empiredb archive-push %p' "
                "AND (SELECT archived_count>0 FROM pg_catalog.pg_stat_archiver))")
    return observed=='t'


def private_credential(password: str) -> None:
    if not password or ":" in password or "\n" in password:
        raise ValueError("BAD_PASSWORD")
    VAULT.mkdir(mode=0o700,parents=True,exist_ok=False)
    os.chmod(VAULT,0o700)
    os.chown(VAULT,0,0)
    fd=os.open(PASSFILE,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as handle:
        handle.write(f"/var/run/postgresql:5432:empiredb:{LOGIN}:{password}\n")
        handle.flush()
        os.fsync(handle.fileno())


def live_login_proof(password: str) -> bool:
    import psycopg
    with psycopg.connect(
        host="/var/run/postgresql",port=5432,dbname=DB,user=LOGIN,
        password=password,connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='3000ms'")
            row=cur.execute(
                "SELECT session_user,current_user,"
                "pg_catalog.has_table_privilege(session_user,"
                "'public.commercial_events','SELECT'),"
                "pg_catalog.has_table_privilege(session_user,"
                "'public.fulfilment_orders','SELECT'),"
                "pg_catalog.has_table_privilege(session_user,"
                "'public.buyers','SELECT')"
            ).fetchone()
            if row != (LOGIN,LOGIN,False,False,False):
                return False
            cur.execute("SET LOCAL ROLE "+ROLE)
            # Do NOT grant direct EXECUTE on the trusted session tenant
            # resolver. Only the SECURITY DEFINER reader invokes it internally.
            row=cur.execute(
                "SELECT count(*) FROM public.read_predictive_revenue_event_v1("
                "%s::uuid,%s::text)",
                ("00000000-0000-4000-8000-000000000000",TENANT),
            ).fetchone()
            # An absent probe UUID checks the role works; this never verifies
            # actual financial source rows or claims zero recognised revenue.
            return row==(0,)


def main(argv: list[str]|None=None) -> int:
    args=sys.argv[1:] if argv is None else argv
    if args not in (
        ["--preflight"],["--apply-approved-one-tenant-login"]
    ):
        print("REV052_STATUS=HOLD_EXACT_APPROVAL_FLAG_REQUIRED")
        return 3
    if os.geteuid()!=0:
        print("REV052_STATUS=HOLD_ROOT_LOCAL_SESSION_REQUIRED")
        return 3
    apply=args==["--apply-approved-one-tenant-login"]
    changed=False
    committed=False
    stage="LOCK_PREFLIGHT"
    try:
        with LOCK.open("a+") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            stage="CATALOG_READONLY"
            source=catalog()
            required=(
                "canonical","postgres18","tenant_resolver",
                "reader_capability","reader_function","login_absent",
                "capability_unassigned","tenant_bind_absent",
                "one_active_founder_owner","known_existing_tenant",
                "financial_tables_exist","capability_table_read_denied",
                "hba_valid","hba_file_matches","data_directory_matches"
            )
            if not all(source.get(k) is True for k in required):
                print("REV052_STATUS=HOLD_DATABASE_SCOPE_OR_FOUNDER_TENANT_NOT_PROVEN")
                print("REV052_FAILED_PREREQUISITES="+",".join(k for k in required if source.get(k) is not True))
                return 2
            if VAULT.exists():
                print("REV052_STATUS=HOLD_PRIVATE_CREDENTIAL_VAULT_ALREADY_EXISTS")
                return 2
            stage="HBA_FILE_READONLY"
            st,original=strict_hba()
            stage="BACKUP_ARCHIVE_READONLY"
            if not backup_ready() or not archive_matches_active_repository():
                print("REV052_STATUS=HOLD_RECENT_BACKUP_OR_ARCHIVE_NOT_PROVEN")
                return 2
            stage="RELEASE_SOURCE_READONLY"
            if apply and not reviewed_script():
                print("REV052_STATUS=HOLD_UNREVIEWED_RELEASE_SOURCE")
                return 2
            if not apply:
                print("REV052_STATUS=READY_ONE_FOUNDER_TENANT_RESTRICTED_LOGIN")
                print("REV052_EXECUTION_AUTHORITY=none")
                return 0

            stage="HBA_BACKUP"
            save_hba_backup(original)
            amended=PREFIX.encode("ascii")+original
            stage="HBA_UPDATE"
            write_hba(amended,st)
            changed=True
            stage="HBA_RELOAD_CHECK"
            active_hba_reload()
            if pg("SELECT count(*) FROM pg_catalog.pg_hba_file_rules WHERE error IS NOT NULL")!="0":
                raise RuntimeError("POST_RELOAD_HBA_PARSE_ERROR")
            password=secrets.token_urlsafe(48)
            verifier=scram_verifier(password)
            stage="CREDENTIAL_CREATION"
            private_credential(password)
            # Exact bounded DB mutation in one atomic transaction.
            stage="LOGIN_DB_TRANSACTION"
            pg(provision_sql(verifier))
            committed=True
            # Admin-only readback: role tenant binding, no customer records.
            stage="TENANT_BINDING_READBACK"
            binding=pg(
                "SELECT count(*) FROM public.empire_tenant_role_bindings "
                f"WHERE role_name='{LOGIN}' AND tenant_id='{TENANT}'::uuid "
                "AND active AND nullif(btrim(evidence_ref),'') IS NOT NULL"
            )
            if binding!='1':
                raise RuntimeError("DEDICATED_TENANT_BINDING_READBACK_FAILED")
            stage="AUTHENTICATED_FUNCTION_PROOF"
            if not live_login_proof(password):
                raise RuntimeError("AUTHENTICATED_TENANT_FUNCTION_PROOF_NOT_VERIFIED")
            print("REV052_TENANT_BOUND_AUTHENTICATED_FUNCTION_PROOF=PASS")
            print("REV052_PRIVATE_CREDENTIAL_SERVER_ONLY=YES")
            print("REV052_REVENUE_EVENT_FETCHED=NO")
            print("REV052_FINANCIAL_WRITE_AUTHORITY=NO")
            print("REV052_STATUS=ONE_RESTRICTED_EVIDENCE_LOGIN_VERIFIED")
            return 0
    except Exception:
        if changed and not committed:
            try:
                # Restore only our exact additive HBA change. A changed
                # bystander file is never overwritten blindly.
                if HBA.read_bytes()==PREFIX.encode("ascii")+original:
                    write_hba(original,st)
                    active_hba_reload()
                else:
                    print("REV052_HBA_RECONCILIATION_REQUIRED=YES")
            except Exception:
                print("REV052_HBA_RECONCILIATION_REQUIRED=YES")
            if VAULT.exists():
                try:
                    if PASSFILE.is_file() and not PASSFILE.is_symlink():
                        PASSFILE.unlink()  # Aborted DB transaction, no login.
                    VAULT.rmdir()
                except OSError:
                    print("REV052_UNUSED_VAULT_RECONCILIATION_REQUIRED=YES")
        print("REV052_FAILURE_STAGE="+stage)
        print("REV052_STATUS=HOLD_OR_UNVERIFIED_NO_BLIND_RETRY")
        if committed:
            print("REV052_DATABASE_TRANSACTION_COMMITTED_VERIFY_CREDENTIALS=REQUIRED")
        return 4


if __name__=="__main__":
    raise SystemExit(main())
