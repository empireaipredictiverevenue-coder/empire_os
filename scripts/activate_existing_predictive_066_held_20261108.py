"""Founder-scoped release of original Predictive Cloud migration 066 (HELD only).

No live customer admission. Corrects solely the obsolete 066 migrator-member
preflight to the exact original 049 trusted migrator login contract, creates
the prerequisite NOLOGIN reader in the SAME 066 transaction, and leaves
all original migration SQL unchanged on disk. No new service or login.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ORIGINAL=Path("/srv/empire_os/migrations/empiredb/066_predictive_source_rights_inventory_held.sql")
ORIGINAL_SHA="56d1f468132915603750e39e9cf7d419884cff7c4d35844b4d62108290dad34b"
TRUSTED_049=Path("/srv/empire_os/migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql")
TRUSTED_049_SHA="f48ed148e7d50265671efaa56c1fc0ea10bb1bf3d3a8b2829970d9383720a9fe"
BACKUP_DIR=Path("/var/backups/empiredb/predictive-source-rights-066-20261108")
BACKUP=BACKUP_DIR/"empiredb-before-predictive-066.dump"
RECEIPT=BACKUP_DIR/"activation_receipt.json"

OLD_GUARD=""" ) OR EXISTS (
   SELECT 1 FROM pg_catalog.pg_auth_members
   WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
 ) THEN RAISE EXCEPTION 'V4_066_RESTRICTED_OWNER_REQUIRED';"""

NEW_GUARD=""" ) OR
 (SELECT count(*) FROM pg_catalog.pg_auth_members AS m
  JOIN pg_catalog.pg_roles AS parent ON parent.oid=m.roleid
  WHERE parent.rolname='empiredb_migrator') <> 1
 OR NOT EXISTS(
   SELECT 1 FROM pg_catalog.pg_auth_members AS m
   JOIN pg_catalog.pg_roles AS parent ON parent.oid=m.roleid
   JOIN pg_catalog.pg_roles AS member ON member.oid=m.member
   WHERE parent.rolname='empiredb_migrator'
     AND member.rolname='empiredb_migrator_login'
     AND member.rolcanlogin AND member.rolinherit
     AND NOT member.rolsuper AND NOT member.rolbypassrls
     AND NOT member.rolcreatedb AND NOT member.rolcreaterole
     AND m.inherit_option AND m.set_option AND NOT m.admin_option
 ) THEN RAISE EXCEPTION 'V4_066_RESTRICTED_OWNER_REQUIRED';"""

ROLE_INSERT="""SET LOCAL lock_timeout='3s';
CREATE ROLE empire_predictive_rights_reader
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;"""

SQL_PREFLIGHT="""
SELECT
 current_database()='empiredb',
 current_setting('server_version_num')::int / 10000 = 18,
 NOT pg_is_in_recovery(),
 (SELECT count(*)=1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
  AND NOT rolcreaterole AND NOT rolbypassrls),
 (SELECT count(*)=1 FROM pg_catalog.pg_auth_members AS m
  JOIN pg_catalog.pg_roles AS parent ON parent.oid=m.roleid
  WHERE parent.rolname='empiredb_migrator'),
 (SELECT count(*)=1 FROM pg_catalog.pg_auth_members AS m
  JOIN pg_catalog.pg_roles AS parent ON parent.oid=m.roleid
  JOIN pg_catalog.pg_roles AS member ON member.oid=m.member
  WHERE parent.rolname='empiredb_migrator'
    AND member.rolname='empiredb_migrator_login'
    AND member.rolcanlogin AND member.rolinherit
    AND NOT member.rolsuper AND NOT member.rolbypassrls
    AND NOT member.rolcreatedb AND NOT member.rolcreaterole
    AND m.inherit_option AND m.set_option AND NOT m.admin_option),
 has_schema_privilege('empiredb_migrator','public','CREATE'),
 has_schema_privilege('empiredb_migrator','public','USAGE'),
 (SELECT count(*)=0 FROM pg_catalog.pg_roles
  WHERE rolname IN ('empire_predictive_rights_reader',
                    'empire_predictive_rights_login')),
 pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held') IS NULL
 AND pg_catalog.to_regclass('public.empire_predictive_source_revocations_held') IS NULL
 AND pg_catalog.to_regprocedure(
     'public.read_empire_predictive_source_rights_held(uuid,text,text)') IS NULL;
"""

SQL_READBACK="""
SELECT
  pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held') IS NOT NULL,
  pg_catalog.to_regclass('public.empire_predictive_source_revocations_held') IS NOT NULL,
  pg_catalog.to_regprocedure('public.read_empire_predictive_source_rights_held(uuid,text,text)') IS NOT NULL,
  (SELECT count(*)=1 FROM pg_catalog.pg_roles WHERE rolname='empire_predictive_rights_reader'
   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
   AND NOT rolcreatedb AND NOT rolcreaterole),
  (SELECT relrowsecurity AND relforcerowsecurity
     FROM pg_catalog.pg_class WHERE oid=pg_catalog.to_regclass(
       'public.empire_predictive_source_rights_candidate_held')),
  (SELECT relrowsecurity AND relforcerowsecurity
     FROM pg_catalog.pg_class WHERE oid=pg_catalog.to_regclass(
       'public.empire_predictive_source_revocations_held')),
  NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_class AS c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) AS acl
    WHERE c.oid=pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held')
      AND acl.grantee=0 AND acl.privilege_type='SELECT'),
  NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_class AS c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) AS acl
    WHERE c.oid=pg_catalog.to_regclass('public.empire_predictive_source_revocations_held')
      AND acl.grantee=0 AND acl.privilege_type='SELECT'),
  (SELECT COUNT(*)=0 FROM pg_catalog.pg_auth_members AS m
     JOIN pg_catalog.pg_roles AS parent ON parent.oid=m.roleid
     WHERE parent.rolname='empire_predictive_rights_reader'),
  (SELECT count(*)=0 FROM pg_catalog.pg_roles
     WHERE rolname='empire_predictive_rights_login'),
  has_function_privilege('empire_predictive_rights_reader',
    'public.read_empire_predictive_source_rights_held(uuid,text,text)','EXECUTE'),
  NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_proc AS proc
    CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(proc.proacl,pg_catalog.acldefault('f',proc.proowner))) AS acl
    WHERE proc.oid=pg_catalog.to_regprocedure(
        'public.read_empire_predictive_source_rights_held(uuid,text,text)')
      AND acl.grantee=0 AND acl.privilege_type='EXECUTE'),
  NOT has_table_privilege('empire_predictive_rights_reader',
       'public.empire_predictive_source_rights_candidate_held','SELECT');
"""

def h(raw:bytes)->str:
    return sha256(raw).hexdigest()

def original_sql()->str:
    for p,expected in ((ORIGINAL,ORIGINAL_SHA),(TRUSTED_049,TRUSTED_049_SHA)):
        if p.is_symlink() or not p.is_file() or h(p.read_bytes())!=expected:
            raise RuntimeError("original_owner_sql_sha_changed")
    original=ORIGINAL.read_text()
    if (original.count(OLD_GUARD)!=1 or original.count("SET LOCAL lock_timeout='3s';")!=1
            or not original.startswith("-- EmpireOS Predictive Cloud 066")
            or not original.rstrip().endswith("COMMIT;")):
        raise RuntimeError("original_066_contract_changed")
    trusted=TRUSTED_049.read_text()
    for fragment in (
        "member.rolname='empiredb_migrator_login'",
        "m.inherit_option AND m.set_option AND NOT m.admin_option",
        "AND member.rolcanlogin AND member.rolinherit",
    ):
        if fragment not in trusted:
            raise RuntimeError("original_049_trusted_migrator_contract_changed")
    sql=original.replace(OLD_GUARD,NEW_GUARD,1)
    sql=sql.replace("SET LOCAL lock_timeout='3s';",ROLE_INSERT,1)
    return sql

def run_sql(sql:str,*,live:bool)->str:
    cmd=(["runuser","-u","postgres","--"] if live else [])+[
        "psql","-XAt","-w","-v","ON_ERROR_STOP=1",
        "-d","empiredb" if live else "empire_v4_outbox_fixture",
        "-c",sql]
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                     text=True,timeout=35)
    if p.returncode:
        # Suppress potentially sensitive DB diagnostic details.
        raise RuntimeError("postgres_guard_or_sql_execution_failed")
    return p.stdout.strip()

def preflight()->dict:
    sql=original_sql()
    output=run_sql(SQL_PREFLIGHT,live=True)
    fields=output.split("|")
    if len(fields)!=10 or any(x not in ("t","f") for x in fields):
        raise RuntimeError("live_owner_preflight_response_invalid")
    return dict(ready=all(x=="t" for x in fields),
                flags=[x=="t" for x in fields],
                original_066_sha=ORIGINAL_SHA,
                release_sql_sha=h(sql.encode()),production_changes=False)

def rehearsal()->dict:
    if os.geteuid()==0 or os.environ.get("PGHOST")!="localhost" or not int(os.environ.get("PGPORT","0"))>=5433:
        raise RuntimeError("isolated_postgres_fixture_required")
    directory=run_sql.__globals__["subprocess"].run(
        ["psql","-XAt","-w","-d","postgres","-c","SHOW data_directory"],
        capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    if not (directory.startswith("/tmp/pg_virtualenv.") and directory.endswith("/data/18/regress")):
        raise RuntimeError("not_pg_virtualenv_temporary_postgres")
    setup="""CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    CREATE ROLE empiredb_migrator_login LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    GRANT empiredb_migrator TO empiredb_migrator_login WITH INHERIT TRUE, SET TRUE, ADMIN FALSE;"""
    p=subprocess.run(["psql","-Xq","-v","ON_ERROR_STOP=1","-d","postgres","-c",setup],
                     stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=10)
    if p.returncode:raise RuntimeError("isolated_role_fixture_failed")
    p=subprocess.run(["createdb","-E","UTF8","-T","template0","empire_v4_outbox_fixture"],
                     capture_output=True,timeout=10)
    if p.returncode:raise RuntimeError("isolated_database_fixture_failed")
    run_sql("GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator",live=False)
    pre=subprocess.run(["psql","-XAt","-d","empire_v4_outbox_fixture","-c",
        "SELECT count(*) FROM pg_catalog.pg_auth_members AS m JOIN pg_catalog.pg_roles AS r ON r.oid=m.roleid WHERE r.rolname='empiredb_migrator'"],
        capture_output=True,text=True,check=True,timeout=10)
    if pre.stdout.strip()!="1":raise RuntimeError("existing_production_membership_not_rehearsed")
    # Original 049-compatible preflight must reject *any* extra role member.
    run_sql(
        "CREATE ROLE untrusted_066_fixture_login LOGIN;"
        "GRANT empiredb_migrator TO untrusted_066_fixture_login",
        live=False)
    rejected=subprocess.run(
        ["psql","-Xq","-v","ON_ERROR_STOP=1","-d","empire_v4_outbox_fixture"],
        input=original_sql(),capture_output=True,text=True,timeout=20)
    if rejected.returncode==0:
        raise RuntimeError("untrusted_extra_migrator_member_was_not_rejected")
    no_object=subprocess.run(
        ["psql","-XAt","-w","-d","empire_v4_outbox_fixture","-c",
         "SELECT to_regclass('public.empire_predictive_source_rights_candidate_held') IS NULL,"
         "(SELECT count(*)=0 FROM pg_catalog.pg_roles WHERE rolname='empire_predictive_rights_reader')"],
        capture_output=True,text=True,check=True,timeout=10)
    if no_object.stdout.strip()!="t|t":
        raise RuntimeError("failed_066_attempt_did_not_rollback_atomically")
    run_sql(
        "REVOKE empiredb_migrator FROM untrusted_066_fixture_login;"
        "DROP ROLE untrusted_066_fixture_login",
        live=False)
    p=subprocess.run(["psql","-Xq","-v","ON_ERROR_STOP=1",
                      "-d","empire_v4_outbox_fixture"],
                     input=original_sql(),capture_output=True,text=True,timeout=20)
    if p.returncode:
        raise RuntimeError("original_066_scoped_fixture_rehearsal_failed")
    result=run_sql(SQL_READBACK,live=False).split("|")
    if len(result)!=13 or any(x!="t" for x in result):
        raise RuntimeError("isolated_066_rls_or_role_readback_failed")
    # Real 066 requires the reader to be a dedicated NOLOGIN capability.
    return dict(result="ISOLATED_ORIGINAL_066_WITH_049_COMPAT_REHEARSED",
                checks=len(result),migration_sql_sha=h(original_sql().encode()),
                production_changes=False,source_rights_granted=False)

def backup_before_apply()->dict:
    if BACKUP_DIR.exists() or BACKUP_DIR.is_symlink():
        raise RuntimeError("prior_backup_or_release_artifact_exists")
    if not BACKUP_DIR.parent.is_dir() or BACKUP_DIR.parent.is_symlink():
        raise RuntimeError("owner_backup_parent_untrusted")
    BACKUP_DIR.mkdir(mode=0o700)
    os.chmod(BACKUP_DIR,0o700)
    fd=os.open(BACKUP,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as f:
        p=subprocess.run(["runuser","-u","postgres","--","pg_dump",
             "-Fc","-d","empiredb"],
             stdout=f,stderr=subprocess.PIPE,timeout=120)
        f.flush()
        os.fsync(f.fileno())
        if p.returncode:raise RuntimeError("pre_066_logical_backup_failed")
    if BACKUP.stat().st_size<10000 or BACKUP.stat().st_size>2_000_000_000:
        raise RuntimeError("pre_066_logical_backup_size_out_of_bounds")
    scan=subprocess.run(["pg_restore","--list",str(BACKUP)],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    if scan.returncode or b"TABLE" not in scan.stdout:
        raise RuntimeError("pre_066_logical_backup_catalog_invalid")
    return dict(path=str(BACKUP),sha256=h(BACKUP.read_bytes()),
                bytes=BACKUP.stat().st_size,pg_restore_catalog_valid=True)

def apply()->dict:
    if os.geteuid()!=0:raise RuntimeError("restricted_founder_root_operator_required")
    pre=preflight()
    if not pre["ready"]:
        raise RuntimeError("original_049_compat_066_preflight_not_ready")
    # No attempt to change the original migrator login or access policy.
    snapshot=backup_before_apply()
    # Guard against concurrent changes after the backup.
    if not preflight()["ready"]:
        raise RuntimeError("original_066_preimage_changed_after_snapshot")
    p=subprocess.run(["runuser","-u","postgres","--","psql",
                      "-Xq","-w","-v","ON_ERROR_STOP=1","-d","empiredb"],
                     input=original_sql(),capture_output=True,text=True,timeout=40)
    if p.returncode:
        raise RuntimeError("original_066_migration_transaction_failed_no_release_claim")
    flags=run_sql(SQL_READBACK,live=True).split("|")
    if len(flags)!=13 or any(x!="t" for x in flags):
        raise RuntimeError("postcommit_acl_or_rls_contract_not_verified")
    receipt=dict(result="ORIGINAL_066_HELD_INSTALLED_AND_CATALOG_VERIFIED",
                 installed_at=datetime.now(timezone.utc).isoformat(),
                 original_066_sha=ORIGINAL_SHA, trusted_049_sha=TRUSTED_049_SHA,
                 release_sql_sha=pre["release_sql_sha"],
                 pre_migration_backup=snapshot,
                 rls_force_verified=True,reader_nologin_verified=True,
                 original_migrator_membership_preserved=True,
                 customer_delivery_enabled=False,source_admitted=False,
                 new_login_created=False,server_restart=False)
    fd=os.open(RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(receipt,f,sort_keys=True,indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return receipt

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight-read-only",action="store_true")
    group.add_argument("--rehearse-isolated",action="store_true")
    group.add_argument("--apply-founder-approved",action="store_true")
    a=ap.parse_args()
    if a.preflight_read_only: result=preflight()
    elif a.rehearse_isolated: result=rehearsal()
    else:result=apply()
    print(json.dumps(result,sort_keys=True))
