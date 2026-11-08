"""Independent original CRM tenant/ICH HELD binding receipt verifier (READ ONLY).

Refuses wrong owner, wrong hash, leaked credentials, missing privileges,
extra reader permissions, false source admission or changed backup.
Prints no tenant identifiers, passwords, DSNs, or private row data.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
from uuid import UUID

from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader

D=Path("/var/backups/empiredb/predictive-source-tenant-held-20261108")
RECEIPT=D/"founder_held_binding_receipt.json"
DSN=D/"rights_reader_dsn"
EXPECTED_SOURCE="31787934624aac98439d48603641951d910e6df96880de9dafe4e35cb2614b5d"
EXPECTED_PURPOSE="PRIVATE_PREDICTIVE_RESEARCH_ONLY"

JOIN="""m.role='owner' AND m.status='active' AND m.revoked_at IS NULL
  AND m.verified_at<=CURRENT_TIMESTAMP
  AND (m.valid_until IS NULL OR m.valid_until>CURRENT_TIMESTAMP)
  AND length(btrim(m.evidence_ref))>0
  AND c.status='active' AND c.password_change_required=false
  AND c.invitation_redeemed_at IS NOT NULL
  AND c.verified_at<=CURRENT_TIMESTAMP AND length(btrim(c.evidence_ref))>0
  AND c.invitation_tenant_id=m.tenant_id AND c.subject=m.subject"""

def query(sql):
    p=subprocess.run(["runuser","-u","postgres","--","psql",
                     "-XAt","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-c",sql],
                    capture_output=True,text=True,timeout=15)
    if p.returncode:
        raise RuntimeError("read_only_postgres_verifier_guard_failed")
    return p.stdout.strip()

def sha_file(p):
    h=sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""):
            h.update(c)
    return h.hexdigest()

def check_private(p,mode):
    if (p.is_symlink() or not p.exists() or p.stat().st_uid!=0
        or stat.S_IMODE(p.stat().st_mode)!=mode):
        raise RuntimeError("root_only_release_custody_invalid")

def verify():
    if os.geteuid()!=0:raise RuntimeError("independent_root_owner_read_required")
    check_private(D,0o700)
    check_private(RECEIPT,0o600)
    check_private(DSN,0o600)
    receipt=json.loads(RECEIPT.read_text())
    if (receipt.get("result")!="ORIGINAL_CRM_TENANT_SOURCE_RIGHTS_PENDING_HELD_BOUND"
        or receipt.get("source_review_state")!="PENDING"
        or receipt.get("original_ich_source_digest")!=EXPECTED_SOURCE
        or receipt.get("independent_signed_legal_attestation") is not False
        or receipt.get("source_admission_authorized") is not False
        or receipt.get("external_redistribution_authorized") is not False
        or receipt.get("customer_forecast_verified") is not False):
        raise RuntimeError("founder_source_review_status_promoted")
    for name,expected in receipt["backup_files"].items():
        if name not in ("empiredb-pre-bind.dump","postgres-globals-pre-bind.sql"):
            raise RuntimeError("unexpected_backup_manifest_item")
        p=D/name
        check_private(p,0o600)
        if (p.stat().st_size!=expected.get("bytes")
            or sha_file(p)!=expected.get("sha256")):
            raise RuntimeError("original_database_backup_hash_changed")
    catalog=subprocess.run(["pg_restore","--list",str(D/"empiredb-pre-bind.dump")],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    if catalog.returncode or b"TABLE" not in catalog.stdout:
        raise RuntimeError("backup_catalog_corrupt")
    # Founder tenant comes solely from the current canonical 041+042 authority,
    # not from CLI, incoming documents, cached JWT, or a duplicated local store.
    owners=query(f"""SELECT m.tenant_id FROM public.empire_crm_tenant_memberships m
       JOIN public.empire_crm_login_credentials c ON c.subject=m.subject
       WHERE {JOIN}""").splitlines()
    if len(owners)!=1 or str(UUID(owners[0]))!=owners[0]:
        raise RuntimeError("real_canonical_owner_ambiguous_or_revoked")
    tenant=owners[0]
    if sha256(tenant.encode()).hexdigest()!=receipt.get("actual_crm_tenant_sha256"):
        raise RuntimeError("bound_tenant_identity_not_original_crm")
    # The protected receipt is still data, not SQL or execution authority.
    import re
    if not re.fullmatch(r"[a-f0-9]{64}",receipt.get("rights_policy_sha256","")):
        raise RuntimeError("protected_policy_receipt_digest_untrusted")
    # Exactly one immutable PENDING rights candidate, owned by original 066
    # migrator, with rights digest anchored to the official policy receipt.
    evidence=query(f"""SELECT
      count(*),
      bool_and(source_review_state='PENDING'),
      bool_and(execution_authority='none'),
      bool_and(tenant_id='{tenant}'::uuid),
      bool_and(source_evidence_digest='{EXPECTED_SOURCE}'),
      bool_and(permitted_purpose='{EXPECTED_PURPOSE}'),
      bool_and(rights_document_digest='{receipt["rights_policy_sha256"]}'),
      bool_and(evidence_observed_at<=now() AND valid_until>now())
      FROM public.empire_predictive_source_rights_candidate_held""")
    if evidence!="1|t|t|t|t|t|t|t":
        raise RuntimeError("rights_candidate_not_exact_original_tenant_pending")
    if query("SELECT count(*) FROM public.empire_predictive_source_revocations_held")!="0":
        raise RuntimeError("unexpected_revocation_or_migration_side_effect")
    acl=query("""SELECT
      (SELECT count(*)=1 FROM pg_catalog.pg_roles WHERE rolname='empire_predictive_rights_login'
        AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
        AND NOT rolbypassrls
        AND rolvaliduntil>now() AND rolvaliduntil<=now()+interval '8 days'),
      (SELECT count(*)=1 FROM pg_catalog.pg_auth_members m
         JOIN pg_catalog.pg_roles parent ON parent.oid=m.roleid
         JOIN pg_catalog.pg_roles member ON member.oid=m.member
         WHERE parent.rolname='empire_predictive_rights_reader'
           AND member.rolname='empire_predictive_rights_login'
           AND m.inherit_option AND NOT m.set_option AND NOT m.admin_option),
      (SELECT count(*)=1 FROM pg_catalog.pg_auth_members m
        WHERE m.member=(SELECT oid FROM pg_catalog.pg_roles
                        WHERE rolname='empire_predictive_rights_login')),
      has_function_privilege('empire_predictive_rights_login',
         'public.read_empire_predictive_source_rights_held(uuid,text,text)','EXECUTE'),
      NOT has_table_privilege('empire_predictive_rights_login',
         'public.empire_predictive_source_rights_candidate_held','SELECT'),
      NOT has_table_privilege('empire_predictive_rights_login',
         'public.empire_predictive_source_rights_candidate_held','INSERT'),
      NOT has_table_privilege('empire_predictive_rights_login',
         'public.empire_predictive_source_revocations_held','INSERT')""")
    if acl!="t|t|t|t|t|t|t":
        raise RuntimeError("dedicated_rights_login_acl_excessive")
    dsn=DSN.read_text().strip()
    if not dsn or len(dsn)>1000:
        raise RuntimeError("dedicated_private_reader_dsn_invalid")
    from psycopg.conninfo import conninfo_to_dict
    options=conninfo_to_dict(dsn)
    if (options.get("host")!="127.0.0.1"
        or options.get("port")!="5432"
        or options.get("dbname")!="empiredb"
        or options.get("user")!="empire_predictive_rights_login"
        or not options.get("password")):
        raise RuntimeError("dedicated_reader_connection_must_be_original_loopback")
    reader=EmpireDbHeldSourceRightsReader(dsn)
    genuine=reader(tenant,EXPECTED_SOURCE)
    other=reader(str(UUID(int=UUID(tenant).int ^ 1)),EXPECTED_SOURCE)
    fake=reader(tenant,"f"*64)
    if (genuine is None or genuine.decision!="PENDING_HELD"
        or genuine.tenant_id!=tenant
        or genuine.real_rights_independently_verified
        or genuine.source_admission_authorized
        or genuine.execution_authority!="none"
        or other is None or other.decision!="NO_SOURCE_RIGHTS_HELD"
        or fake is None or fake.decision!="NO_SOURCE_RIGHTS_HELD"):
        raise RuntimeError("original_reader_held_identity_or_isolation_failed")
    return {"result":"INDEPENDENT_GENUINE_CRM_TENANT_ICH_HELD_BINDING_VERIFIED",
            "canonical_owner_tenant_verified":True,
            "original_restricted_reader_verified":True,
            "official_ich_evidence_hash_verified":True,
            "public_reuse_policy_hash_bound":True,
            "cross_tenant_rejected":True,
            "wrong_source_rejected":True,
            "backup_integrity_and_catalog_verified":True,
            "restricted_login_acl_verified":True,
            "source_review_state":"PENDING_HELD",
            "customer_source_admitted":False,
            "customer_forecast_enabled":False,
            "production_changes":False}

if __name__=="__main__":
    print(json.dumps(verify(),sort_keys=True))
