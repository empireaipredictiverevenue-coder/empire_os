"""Independent read-only operator preflight for existing 066 HELD migration.

No credentials emitted, no database changes, no migrations, no service calls.
"""
from __future__ import annotations
import json
import subprocess

SQL = """
SELECT
 current_database() = 'empiredb',
 current_setting('server_version_num')::int / 10000 = 18,
 NOT pg_is_in_recovery(),
 (SELECT count(*)=1 FROM pg_catalog.pg_roles
  WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
  AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls),
 (SELECT count(*)=0 FROM pg_catalog.pg_auth_members
  WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles
                WHERE rolname='empiredb_migrator')),
 (SELECT has_schema_privilege('empiredb_migrator','public','CREATE')),
 (SELECT has_schema_privilege('empiredb_migrator','public','USAGE')),
 (SELECT count(*)=0 FROM pg_catalog.pg_roles
  WHERE rolname IN ('empire_predictive_rights_reader',
                    'empire_predictive_rights_login')),
 (pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held') IS NULL
  AND pg_catalog.to_regclass('public.empire_predictive_source_revocations_held') IS NULL
  AND pg_catalog.to_regprocedure('public.read_empire_predictive_source_rights_held(uuid,text,text)') IS NULL),
 (SELECT count(*) FROM pg_catalog.pg_stat_activity
  WHERE datname='empiredb' AND state='active');
"""
def inspect():
    cmd=["sudo","-n","runuser","-u","postgres","--","psql",
         "-XAt","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-c",SQL]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=12)
    if p.returncode:
        return {"result":"OWNER_SQL_PREFLIGHT_UNAVAILABLE","production_changes":False}
    rows=p.stdout.strip().splitlines()
    if len(rows)!=1:raise RuntimeError("unexpected_owner_metadata_row_count")
    parts=rows[0].split("|")
    if len(parts)!=10:raise RuntimeError("unexpected_owner_metadata_fields")
    names=("correct_db","postgresql_18","writable_primary","migrator_restricted",
           "migrator_has_no_members","migrator_public_create","migrator_public_usage",
           "new_rights_roles_absent","source_rights_objects_absent")
    if any(v not in ("t","f") for v in parts[:9]) or not parts[9].isdigit():
        raise RuntimeError("unexpected_owner_metadata_values")
    result=dict(zip(names,[v=="t" for v in parts[:9]]))
    result.update(active_sessions_count=int(parts[9]),
                  exact_migration_install_ready=all(v=="t" for v in parts[:9]),
                  changes=False, purpose="INSTALL_ORIGINAL_066_HELD_ONLY",
                  source_authority=False, customer_delivery=False)
    return result
if __name__=="__main__":
    print(json.dumps(inspect(),sort_keys=True))
