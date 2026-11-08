"""Independent post-release read-only original 066 verification.

Verifies root-only fresh backup, live SQL definitions, zero held rows, and
missing login's fail-closed function call; no tables or credentials modified.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import subprocess

D=Path("/var/backups/empiredb/predictive-source-rights-066-20261108")
RECEIPT=D/"activation_receipt.json"
BACKUP=D/"empiredb-before-predictive-066.dump"

SQL="""
SELECT
 (SELECT count(*)=0 FROM public.empire_predictive_source_rights_candidate_held),
 (SELECT count(*)=0 FROM public.empire_predictive_source_revocations_held),
 (SELECT c.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
  FROM pg_catalog.pg_class AS c
  WHERE c.oid=pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held')),
 (SELECT p.prosecdef AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
  FROM pg_catalog.pg_proc AS p WHERE p.oid=pg_catalog.to_regprocedure(
    'public.read_empire_predictive_source_rights_held(uuid,text,text)')),
 (SELECT count(*)=0 FROM pg_catalog.pg_auth_members AS m
  WHERE m.roleid=(SELECT oid FROM pg_catalog.pg_roles
    WHERE rolname='empire_predictive_rights_reader')),
 (SELECT count(*)=0 FROM pg_catalog.pg_roles
  WHERE rolname='empire_predictive_rights_login');
"""
def cmd(query:str):
    return subprocess.run(
        ["runuser","-u","postgres","--","psql","-XAt","-w",
         "-v","ON_ERROR_STOP=1","-d","empiredb","-c",query],
        capture_output=True,text=True,timeout=12)

def verify():
    if (D.is_symlink() or not D.is_dir()
            or D.stat().st_uid!=0 or stat.S_IMODE(D.stat().st_mode)!=0o700):
        raise RuntimeError("backup_directory_ownership_or_mode_invalid")
    for p in (RECEIPT,BACKUP):
        if (p.is_symlink() or not p.is_file() or p.stat().st_uid!=0
                or stat.S_IMODE(p.stat().st_mode)!=0o600):
            raise RuntimeError("backup_receipt_or_archive_ownership_invalid")
    receipt=json.loads(RECEIPT.read_text())
    if receipt.get("result")!="ORIGINAL_066_HELD_INSTALLED_AND_CATALOG_VERIFIED":
        raise RuntimeError("original_066_release_receipt_untrusted")
    digest=hashlib.sha256()
    with BACKUP.open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""):
            digest.update(chunk)
    expected=receipt["pre_migration_backup"]
    if (digest.hexdigest()!=expected["sha256"]
            or BACKUP.stat().st_size!=expected["bytes"]):
        raise RuntimeError("fresh_pre_migration_archive_integrity_invalid")
    scan=subprocess.run(["pg_restore","--list",str(BACKUP)],
                        capture_output=True,timeout=20)
    if scan.returncode or b"TABLE" not in scan.stdout:
        raise RuntimeError("fresh_pre_migration_archive_catalog_invalid")
    result=cmd(SQL)
    if result.returncode or result.stdout.strip()!="t|t|t|t|t|t":
        raise RuntimeError("installed_066_owner_security_or_empty_tables_invalid")
    negative=cmd(
        "BEGIN READ ONLY; SELECT * FROM "
        "public.read_empire_predictive_source_rights_held("
        "'00000000-0000-0000-0000-000000000101'::uuid,"
        "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',"
        "'PRIVATE_PREDICTIVE_RESEARCH_ONLY'); ROLLBACK;")
    if negative.returncode==0 or "V4_066_UNTRUSTED_READER_LOGIN" not in negative.stderr:
        raise RuntimeError("untrusted_database_session_not_rejected")
    return dict(
        result="INDEPENDENT_ORIGINAL_066_HELD_POSTRELEASE_VERIFIED",
        archive_integrity_sha256_verified=True,
        archive_restore_catalog_valid=True,
        source_rights_tables_empty=True,
        table_and_definer_owned_by_original_migrator=True,
        dedicated_rights_login_absent=True,
        untrusted_read_denied=True,
        no_tenant_source_admitted=True,production_changes=False)

if __name__=="__main__":
    print(json.dumps(verify(),sort_keys=True))
