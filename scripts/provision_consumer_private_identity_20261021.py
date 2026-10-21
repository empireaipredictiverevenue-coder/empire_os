#!/usr/bin/env python3
"""Dedicated consumer-only EmpireDB login/key custody. PREPARED ONLY.

No production writes without a separate exact-release approval and flag.
The operational private service and public opt-in remain DISABLED throughout.
Default mode: --read-only, requiring privileged local peer access.
An approved apply creates ONLY the login, one restricted role membership and
a root-owned secret vault. Existing roles, tables, HBA, CRM and default ACLs
are never modified. Never print a DSN, password, raw key or SCRAM verifier.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import secrets
import stat
import subprocess
import sys

DB="empiredb"
LOGIN="empire_consumer_optin_login"
WRITER="empire_consumer_optin_writer"
ROOT=Path("/etc/empire/consumer-optin")
PASSFILE=ROOT/"subscriber.pgpass"
KEYFILE=ROOT/"subscriber-keys.json"
LOCKFILE=Path("/run/lock/empire-consumer-identity.lock")
TABLES=(
    "empire_consumer_subscriptions", "empire_consumer_consent_events",
    "empire_consumer_email_suppressions", "empire_consumer_one_time_tokens",
    "empire_consumer_delivery_receipts",
)
EXPECTED_SCHEMA_SHA="fe9da8e0a8871e78103941729fb893c891a542286531a283e0d40f2846026cd1"


def release_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _admin(query: str) -> str:
    # Only root's original local identity may ask the postgres account.
    run=subprocess.run([
        "/usr/sbin/runuser","-u","postgres","--",
        "/usr/bin/psql","-X","-q","-w","-A","-t",
        "-v","ON_ERROR_STOP=1","-h","/var/run/postgresql",
        "-p","5432","-U","postgres","-d",DB,
    ], input=query, capture_output=True, text=True, timeout=25,
       env={"HOME":"/var/lib/postgresql","PATH":"/usr/bin:/bin"})
    if run.returncode:
        raise RuntimeError("ORIGINAL_DB_ADMIN_QUERY_REJECTED")
    return run.stdout.strip()


def check_state() -> dict:
    sql="""
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SELECT pg_catalog.jsonb_build_object(
 'database_correct',current_database()='empiredb' AND NOT pg_is_in_recovery(),
 'owner_role_ready',EXISTS(
     SELECT 1 FROM pg_roles WHERE rolname='empiredb_migrator'
     AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls),
 'writer_role_ready',EXISTS(
     SELECT 1 FROM pg_roles WHERE rolname='empire_consumer_optin_writer'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
     AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
     AND NOT rolreplication),
 'dedicated_login_absent',NOT EXISTS(
     SELECT 1 FROM pg_roles WHERE rolname='empire_consumer_optin_login'),
 'five_tables_forced_rls',(
     SELECT count(*)=5 FROM pg_class c
     JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='public' AND c.relkind='r'
     AND c.relname=ANY(ARRAY[
       'empire_consumer_subscriptions','empire_consumer_consent_events',
       'empire_consumer_email_suppressions','empire_consumer_one_time_tokens',
       'empire_consumer_delivery_receipts'
     ]) AND c.relrowsecurity AND c.relforcerowsecurity
     AND c.relowner='empiredb_migrator'::regrole),
 'five_restricted_policies',(
     SELECT count(*)=5 FROM pg_policies
     WHERE schemaname='public' AND policyname LIKE 'consumer_writer_%'),
 'no_crm_table_select',(
     SELECT count(*)=5 FROM (VALUES
       ('public.empire_consumer_subscriptions'),
       ('public.empire_consumer_consent_events'),
       ('public.empire_consumer_email_suppressions'),
       ('public.empire_consumer_one_time_tokens'),
       ('public.empire_consumer_delivery_receipts')
     ) r(name)
     WHERE NOT has_table_privilege('empiredb_app',r.name,'SELECT')
     AND NOT has_table_privilege('empiredb_readonly',r.name,'SELECT')),
 'hba_local_scram',
     EXISTS(SELECT 1 FROM pg_hba_file_rules
      WHERE type='host' AND address='127.0.0.1'
      AND auth_method='scram-sha-256' AND error IS NULL
      AND ('all'=ANY(database) OR 'empiredb'=ANY(database))
      AND ('all'=ANY(user_name) OR
            'empire_consumer_optin_login'=ANY(user_name))),
 'hba_no_parse_errors',NOT EXISTS(
     SELECT 1 FROM pg_hba_file_rules WHERE error IS NOT NULL),
 'login_membership_absent',NOT EXISTS(
     SELECT 1 FROM pg_auth_members m
     JOIN pg_roles r ON r.oid=m.member
     WHERE r.rolname='empire_consumer_optin_login')
)::text;
ROLLBACK;
"""
    state=json.loads(_admin(sql))
    vault_ok=(not ROOT.is_symlink()
              and not PASSFILE.exists() and not PASSFILE.is_symlink()
              and not KEYFILE.exists() and not KEYFILE.is_symlink()
              and (not ROOT.exists() or (
                 ROOT.is_dir()
                 and stat.S_IMODE(ROOT.stat().st_mode)==0o700
                 and ROOT.stat().st_uid==0)))
    state["secrets_vault_available"]=vault_ok
    return state


def report_read_only() -> dict:
    if os.geteuid()!=0:
        raise RuntimeError("ROOT_OPERATOR_REQUIRED")
    state=check_state()
    return {
        "status": ("READY_FOR_NEW_EXPLICIT_PRIVATE_IDENTITY_APPROVAL"
                   if all(state.values()) else "PRIVATE_IDENTITY_HELD"),
        "schema_release_sha":EXPECTED_SCHEMA_SHA,
        "identity_release_sha":release_sha256(),
        "checks":state,
        "database_writes":False,
        "service_login_created":False,
        "secrets_generated":False,
        "subscriber_capture_enabled":False,
        "outbound_enabled":False,
    }


def scram_verifier(password: str) -> str:
    """Generate a SCRAM verifier so even DBA SQL never sees plaintext."""
    salt=secrets.token_bytes(16)
    iterations=4096
    salted=hashlib.pbkdf2_hmac("sha256",password.encode("ascii"),salt,iterations)
    client=hmac.new(salted,b"Client Key",hashlib.sha256).digest()
    stored=hashlib.sha256(client).digest()
    server=hmac.new(salted,b"Server Key",hashlib.sha256).digest()
    b64=lambda b: base64.b64encode(b).decode("ascii")
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored)}:{b64(server)}"


def role_statement(verifier: str) -> str:
    if not verifier.startswith("SCRAM-SHA-256$4096:") or len(verifier)>200:
        raise RuntimeError("SCRAM_VERIFIER_INVALID")
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/:=$-" for c in verifier):
        raise RuntimeError("SCRAM_VERIFIER_CHARACTERS_INVALID")
    return f"""BEGIN;
SET LOCAL statement_timeout='8s';
SET LOCAL lock_timeout='3s';
DO $guard$
BEGIN
 IF current_database()<>'empiredb'
    OR EXISTS(SELECT 1 FROM pg_roles
              WHERE rolname='empire_consumer_optin_login')
    OR (SELECT count(*) FROM pg_policies
        WHERE schemaname='public' AND policyname LIKE 'consumer_writer_%')<>5
    OR NOT EXISTS(SELECT 1 FROM pg_roles
          WHERE rolname='empire_consumer_optin_writer'
          AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
          AND NOT rolinherit)
    OR (SELECT count(*) FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r'
        AND c.relname=ANY(ARRAY[
          'empire_consumer_subscriptions','empire_consumer_consent_events',
          'empire_consumer_email_suppressions',
          'empire_consumer_one_time_tokens','empire_consumer_delivery_receipts'
        ]) AND c.relrowsecurity AND c.relforcerowsecurity
        AND c.relowner='empiredb_migrator'::regrole)<>5
    OR (SELECT count(*) FROM (VALUES
        ('public.empire_consumer_subscriptions'),
        ('public.empire_consumer_consent_events'),
        ('public.empire_consumer_email_suppressions'),
        ('public.empire_consumer_one_time_tokens'),
        ('public.empire_consumer_delivery_receipts')
       ) t(name)
       WHERE NOT pg_catalog.has_table_privilege(
          'empiredb_app',t.name,'SELECT')
       AND NOT pg_catalog.has_table_privilege(
          'empiredb_readonly',t.name,'SELECT'))<>5
 THEN
    RAISE EXCEPTION 'CONSUMER_PRIVATE_LOGIN_GUARD_HOLD';
 END IF;
END;
$guard$;
CREATE ROLE {LOGIN} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
 NOCREATEDB NOCREATEROLE NOREPLICATION
 CONNECTION LIMIT 5 PASSWORD '{verifier}';
GRANT {WRITER} TO {LOGIN}
 WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
GRANT CONNECT ON DATABASE {DB} TO {LOGIN};
COMMIT;"""


def _write_secret(path: Path, data: bytes) -> None:
    if path.is_symlink() or path.exists():
        raise RuntimeError("PRIVATE_SECRET_PREEXISTS")
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(path,0o600)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def provision(approved_sha: str) -> dict:
    if os.geteuid()!=0 or pwd.getpwuid(os.geteuid()).pw_name!="root":
        raise RuntimeError("ROOT_OPERATOR_REQUIRED")
    if approved_sha!=release_sha256():
        raise RuntimeError("EXACT_PRIVATE_IDENTITY_RELEASE_APPROVAL_REQUIRED")
    # Explicit exclusive single-operator lock. Separate service deployment
    # will need a new release, and is never automatically started here.
    import fcntl
    with LOCKFILE.open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not all(check_state().values()):
            raise RuntimeError("CONSUMER_IDENTITY_PREFLIGHT_HELD")
        if ROOT.exists():
            if not ROOT.is_dir() or list(ROOT.iterdir()):
                raise RuntimeError("PRIVATE_VAULT_NOT_EMPTY")
        else:
            ROOT.mkdir(mode=0o700,parents=True)
            os.chmod(ROOT,0o700)
        password=secrets.token_hex(32)
        keys={
            "key_reference":"consumer-key-v1",
            "email_hmac":secrets.token_hex(32),
            "token_hmac":secrets.token_hex(32),
            "email_encryption":secrets.token_hex(32),
        }
        if len({keys[k] for k in ("email_hmac","token_hmac","email_encryption")})!=3:
            raise RuntimeError("NONUNIQUE_PRIVATE_KEYS")
        # Vault is root-only until service-specific OS identity is approved.
        # If either file creation OR SQL creation fails, clean only the new
        # credentials; never retain a partial set of active secrets.
        try:
            _write_secret(PASSFILE,
                f"127.0.0.1:5432:{DB}:{LOGIN}:{password}\n".encode("ascii"))
            _write_secret(KEYFILE,
                (json.dumps(keys,sort_keys=True)+"\n").encode("ascii"))
            _admin(role_statement(scram_verifier(password)))
        except BaseException:
            # SQL transaction is rolled back by psql on failure. Remove only
            # the two files we ourselves just created. Never drop other DB roles.
            PASSFILE.unlink(missing_ok=True)
            KEYFILE.unlink(missing_ok=True)
            raise
        # Post-commit validation is read only. If it fails, hold and preserve
        # credentials; do NOT attempt unapproved destructive rollback.
        readback=json.loads(_admin("""
SELECT jsonb_build_object(
 'login_role',EXISTS(SELECT 1 FROM pg_roles WHERE rolname=
 'empire_consumer_optin_login' AND rolcanlogin AND NOT rolinherit
 AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 AND NOT rolreplication AND rolconnlimit=5),
 'single_membership',(
 SELECT count(*)=1 FROM pg_auth_members m
 JOIN pg_roles r ON r.oid=m.member
 WHERE r.rolname='empire_consumer_optin_login'),
 'writer_member',pg_has_role('empire_consumer_optin_login',
                            'empire_consumer_optin_writer','MEMBER'),
 'migrator_not_member',NOT pg_has_role('empire_consumer_optin_login',
                                     'empiredb_migrator','MEMBER'),
 'crm_not_member',NOT pg_has_role('empire_consumer_optin_login',
                                'empiredb_app','MEMBER')
)::text;
"""))
        if not all(readback.values()):
            return {
                "status":"PRIVATE_IDENTITY_POSTCOMMIT_REVIEW_REQUIRED",
                "role_created":True, "service_activated":False,
                "credential_details_disclosed":False,
            }
        return {
            "status":"PRIVATE_IDENTITY_PROVISIONED_SERVICE_HELD",
            "role_created":True,
            "only_writer_membership":True,
            "three_distinct_private_keys_staged":True,
            "root_only_vault":True,
            "service_activated":False,
            "subscriber_capture_enabled":False,
            "outbound_enabled":False,
            "credential_details_disclosed":False,
        }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--read-only",action="store_true")
    modes.add_argument("--apply-owner-approved",metavar="EXACT_SHA256")
    opts=parser.parse_args(argv)
    try:
        result=(report_read_only() if opts.read_only
                else provision(opts.apply_owner_approved))
        print(json.dumps(result,sort_keys=True))
        return 0 if result["status"] not in (
            "PRIVATE_IDENTITY_HELD","PRIVATE_IDENTITY_POSTCOMMIT_REVIEW_REQUIRED"
        ) else 3
    except Exception as exc:
        # Never print error details that could contain credentials or SQL.
        print(json.dumps({
            "status":"PRIVATE_IDENTITY_HELD",
            "reason_code":str(exc).splitlines()[0][:95]
                if str(exc).isupper() else "PRIVATE_IDENTITY_OPERATION_FAILED",
            "service_activated":False,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
