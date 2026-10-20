#!/usr/bin/env python3
"""Founder-approved one-login, tenant-bound, local-only SCRAM reader.

Does not apply the separate SQL 056 migration or query any actual orders.
Must be invoked as root, and verified after grants/RLS have been approved.
No credential, DSN, tenant row, password, or SQL detail is logged.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"
FOUNDER = "founder:phil_livesley"
ROLE = "empire_verified_order_tenant_login"
GROUP = "empiredb_tenant_reader"
VAULT = Path("/etc/empire/verified-order-reader")
PASSFILE = VAULT / "reader.pgpass"
DB = "empiredb"

READINESS = """
BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT pg_catalog.jsonb_build_object(
  'correct_db',current_database()='empiredb' AND NOT pg_is_in_recovery(),
  'loopback',current_setting('listen_addresses')='127.0.0.1',
  'founder_owner_one',
    (SELECT count(*)=1 FROM public.empire_crm_tenant_memberships
     WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid
       AND subject='founder:phil_livesley' AND role='owner'
       AND status='active' AND verified_at IS NOT NULL
       AND revoked_at IS NULL
       AND (valid_until IS NULL OR valid_until>clock_timestamp())),
  'founder_bound',
    (SELECT count(*)>=1 FROM public.empire_tenant_role_bindings
     WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid
       AND active AND nullif(btrim(evidence_ref),'') IS NOT NULL),
  'reader_no_login',
    (SELECT count(*)=1 FROM pg_catalog.pg_roles
     WHERE rolname='empiredb_tenant_reader'
       AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
       AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication),
  'login_absent',
    NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname='empire_verified_order_tenant_login'),
  'binding_absent',
    NOT EXISTS (SELECT 1 FROM public.empire_tenant_role_bindings
      WHERE role_name='empire_verified_order_tenant_login'),
  'tenant_member_absent',
    NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members am
      JOIN pg_catalog.pg_roles r ON r.oid=am.member
      WHERE am.roleid='empiredb_tenant_reader'::regrole
        AND r.rolname='empire_verified_order_tenant_login'),
  'five_policies_present',
    (SELECT count(*)=5 FROM pg_catalog.pg_policy p
     WHERE polname IN (
       'order056_outcomes_tenant_select',
       'order056_payment_requests_tenant_select',
       'order056_payment_evidence_tenant_select',
       'order056_escrow_agreements_tenant_select',
       'order056_escrow_evidence_tenant_select')),
  'five_grants_present',
    (SELECT count(*)=5 FROM (VALUES
     ('public.commercial_outcomes'),('public.bsc_payment_requests'),
     ('public.bsc_payment_evidence'),('public.bsc_escrow_agreements'),
     ('public.bsc_escrow_evidence')) t(rel)
     WHERE pg_catalog.has_table_privilege(
       'empiredb_tenant_reader',t.rel,'SELECT')),
  'local_scram_hba',
    EXISTS (SELECT 1 FROM pg_catalog.pg_hba_file_rules
      WHERE type='host' AND address='127.0.0.1'
        AND auth_method='scram-sha-256'
        AND 'all'=ANY(database) AND 'all'=ANY(user_name)
        AND error IS NULL),
  'hba_no_errors',
    NOT EXISTS (SELECT 1 FROM pg_catalog.pg_hba_file_rules
                WHERE error IS NOT NULL),
  'vault_absent',
    TRUE
)::text;
ROLLBACK;
"""


def _admin(sql: str) -> str:
    command = [
        "/usr/sbin/runuser", "-u", "postgres", "--",
        "/usr/bin/psql", "-X", "-q", "-w", "-A", "-t",
        "-v", "ON_ERROR_STOP=1", "-h", "/var/run/postgresql",
        "-p", "5432", "-U", "postgres", "-d", DB,
    ]
    proc = subprocess.run(
        command, input=sql, capture_output=True, text=True,
        timeout=20, env={"PATH": "/usr/bin:/bin", "HOME": "/var/lib/postgresql"},
    )
    if proc.returncode:
        raise RuntimeError("ORIGINAL_ADMIN_SQL_FAILED")
    return proc.stdout.strip()


def preflight() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("ROOT_LOCAL_REQUIRED")
    state = json.loads(_admin(READINESS))
    state["vault_absent"] = not PASSFILE.exists()
    return {
        "schema_version": "empire.commercial.single_tenant_order_login_preflight.v1",
        "status": "READY_FOR_EXPLICIT_FOUNDER_APPROVAL" if all(state.values()) else "HELD",
        "checks": state,
        "payment_or_order_rows_read": False,
        "database_writes": False,
        "outbound_authorized": False,
    }


def _create_vault(password: str) -> None:
    if VAULT.is_symlink() or PASSFILE.exists():
        raise RuntimeError("VAULT_ALREADY_PRESENT")
    VAULT.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(VAULT, 0o700)
    fd = os.open(PASSFILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(f"127.0.0.1:5432:{DB}:{ROLE}:{password}\n")
        os.chmod(PASSFILE, 0o600)
    except BaseException:
        PASSFILE.unlink(missing_ok=True)
        raise


def _create_login_sql(password: str) -> str:
    if len(password) != 64 or any(c not in "0123456789abcdef" for c in password):
        raise ValueError("generated credential must be hex")
    return f"""
BEGIN;
SET LOCAL statement_timeout='7s';
SET LOCAL lock_timeout='3s';
SET LOCAL password_encryption='scram-sha-256';
DO $guard$
BEGIN
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='{ROLE}')
 OR EXISTS(SELECT 1 FROM public.empire_tenant_role_bindings
   WHERE role_name='{ROLE}')
 OR (SELECT count(*) FROM public.empire_crm_tenant_memberships
     WHERE tenant_id='{TENANT}'::uuid AND subject='{FOUNDER}'
       AND role='owner' AND status='active' AND verified_at IS NOT NULL
       AND revoked_at IS NULL) <> 1
 OR (SELECT count(*) FROM pg_catalog.pg_policy
     WHERE polname LIKE 'order056_%') <> 5
 THEN RAISE EXCEPTION 'ORDER_READER_AUTHORITY_OR_RELEASE_CHANGED'; END IF;
END;
$guard$;
CREATE ROLE {ROLE} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
  NOCREATEDB NOCREATEROLE NOREPLICATION
  PASSWORD '{password}';
GRANT {GROUP} TO {ROLE} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
GRANT CONNECT ON DATABASE empiredb TO {ROLE};
INSERT INTO public.empire_tenant_role_bindings
(role_name,tenant_id,active,evidence_ref)
VALUES('{ROLE}','{TENANT}'::uuid,true,
  'FOUNDER_APPROVED_EXACT_ORDER_READER_20261020');
COMMIT;
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in (["--preflight"], ["--apply-founder-approved-one-tenant-login"]):
        print("ORDER_READER_STATUS=HOLD_EXACT_FLAG_REQUIRED")
        return 3
    try:
        report = preflight()
        if args == ["--preflight"]:
            print(json.dumps(report, sort_keys=True))
            return 0
        if report["status"] != "READY_FOR_EXPLICIT_FOUNDER_APPROVAL":
            print("ORDER_READER_STATUS=PRECHECK_HOLD")
            return 2
        password = secrets.token_hex(32)
        _create_vault(password)
        try:
            _admin(_create_login_sql(password))
        except BaseException:
            PASSFILE.unlink(missing_ok=True)
            raise
        print("ORDER_READER_STATUS=ONE_TENANT_LOGIN_CREATED_NEEDS_SESSION_PROOF")
        return 0
    except Exception:
        print("ORDER_READER_STATUS=FAIL_CLOSED_NO_CREDENTIAL_DETAILS")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
