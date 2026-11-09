"""Founder-scoped original Predictive Cloud 066: bind official company research HELD.

Uses the original CRM 041/042 canonical active membership and the original
V4.10 EmpireDbHeldSourceRightsReader. Creates ONLY a dedicated constrained
reader LOGIN + a PENDING HELD rights candidate in already-installed 066.
No public endpoint, migration, new data service, rights attestation, customer
forecast, external redistribution, paid calls, sending or service restart.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
from uuid import UUID

PACKET=Path("/home/ubuntu/empire_worktrees/predictive_cloud_usage_review_20261107/docs/PREDICTIVE_CLOUD_FIRST_PARTY_RESEARCH_COHORT_20261108.json")
PACKET_SHA="18e6dd0947989fceae071940b0177dfad6c7fdf83b2905cfe4b4f73f850da9ef"
POLICY="https://www.gov.uk/government/publications/companies-house-accreditation-to-information-fair-traders-scheme/public-task-copyright-and-crown-copyright"
LOGIN="empire_predictive_rights_login"
CAPABILITY="empire_predictive_rights_reader"
PURPOSE="PRIVATE_PREDICTIVE_RESEARCH_ONLY"
BACKUP=Path("/var/backups/empiredb/predictive-source-tenant-held-20261108")
DSN_PATH=BACKUP/"rights_reader_dsn"
RECEIPT=BACKUP/"founder_held_binding_receipt.json"

def sha(x:bytes)->str:return sha256(x).hexdigest()

class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
    def handle_data(self,value:str):self.parts.append(value)

def source_packet()->dict:
    if PACKET.is_symlink() or sha(PACKET.read_bytes())!=PACKET_SHA:
        raise RuntimeError("original_official_research_packet_changed")
    data=json.loads(PACKET.read_text())
    rows=[x for x in data["records"] if x.get("domain")=="ich-services.co.uk"]
    if len(rows)!=1:raise RuntimeError("original_unique_ich_research_record_missing")
    row=rows[0]
    evidence=row.get("official_uk_source_observation",{})
    fields=evidence.get("public_register_fields",{})
    if (row.get("research_policy")!="PASS_RESEARCH_ONLY"
        or row.get("customer_delivery_authorized") is not False
        or evidence.get("source_kind")!="independent_uk_public_company_register"
        or evidence.get("permitted_purpose_candidate")!=PURPOSE
        or evidence.get("production_source_admitted") is not False
        or evidence.get("source_rights_document_has_been_owner_attested") is not False
        or fields.get("company_number")!="02745893"
        or fields.get("company_name")!="ICH SERVICES LTD"
        or fields.get("company_status")!="Active"
        or any(k not in fields for k in ("sic_codes","registered_address","incorporation_date"))
        or any("@" in str(x) for x in fields.values())):
        raise RuntimeError("original_official_source_provenance_not_held")
    canonical=json.dumps(fields,sort_keys=True,separators=(",",":")).encode()
    digest=sha(canonical)
    if digest!=evidence.get("source_evidence_digest"):
        raise RuntimeError("official_public_register_fields_digest_mismatch")
    observed=datetime.fromisoformat(evidence["source_observed_at_utc"])
    if observed.utcoffset()!=timedelta(0):
        raise RuntimeError("source_observed_at_not_utc")
    if not datetime.now(timezone.utc)-timedelta(days=7)<=observed<=datetime.now(timezone.utc):
        raise RuntimeError("source_evidence_not_recent")
    return {"source_digest":digest,"observed_at":observed.isoformat(),"company_number":"02745893"}

def policy_evidence()->dict:
    p=subprocess.run(["curl","-fsSL","--compressed","--max-time","14",POLICY],
                     capture_output=True,timeout=17)
    if p.returncode or not 10000 <= len(p.stdout) <= 500000:
        raise RuntimeError("official_companies_house_reuse_policy_not_fetched")
    html=HTMLText()
    html.feed(p.stdout.decode("utf-8","strict"))
    txt=" ".join(" ".join(html.parts).lower().split())
    if any(term not in txt for term in (
        "companies house imposes no rules or requirements",
        "public register","third party copyright","crown copyright")):
        raise RuntimeError("official_public_register_reuse_policy_text_changed")
    return {"rights_policy_url":POLICY,
            "rights_document_digest":sha(p.stdout),
            "rights_policy_bytes":len(p.stdout),
            "source_reuse_state":"OFFICIAL_PUBLIC_REGISTER_POLICY_REVIEW_ONLY",
            "independent_signed_license_attestation":False}

def psql(sql:str,*,db:str="empiredb")->str:
    p=subprocess.run(["runuser","-u","postgres","--","psql","-XAt",
                      "-w","-v","ON_ERROR_STOP=1","-d",db,"-c",sql],
                     capture_output=True,text=True,timeout=25)
    if p.returncode:
        raise RuntimeError("bound_066_read_only_pg_catalog_preflight_or_sql_failed")
    return p.stdout.strip()

OWNER_WHERE="""m.role='owner' AND m.status='active' AND m.revoked_at IS NULL
  AND m.verified_at<=CURRENT_TIMESTAMP
  AND (m.valid_until IS NULL OR m.valid_until>CURRENT_TIMESTAMP)
  AND length(btrim(m.evidence_ref))>0
  AND c.status='active' AND c.password_change_required=false
  AND c.invitation_redeemed_at IS NOT NULL
  AND c.verified_at<=CURRENT_TIMESTAMP AND length(btrim(c.evidence_ref))>0
  AND c.invitation_tenant_id=m.tenant_id AND c.subject=m.subject"""

PREFLIGHT=f"""SELECT
 current_database()='empiredb',
 current_setting('server_version_num')::int / 10000=18,
 NOT pg_is_in_recovery(),
 pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held') IS NOT NULL,
 pg_catalog.to_regclass('public.empire_predictive_source_revocations_held') IS NOT NULL,
 pg_catalog.to_regprocedure('public.read_empire_predictive_source_rights_held(uuid,text,text)') IS NOT NULL,
 (SELECT count(*)=1 FROM pg_catalog.pg_roles WHERE rolname='{CAPABILITY}'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
  AND NOT rolcreatedb AND NOT rolcreaterole),
 (SELECT count(*)=0 FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}'),
 (SELECT count(*)=0 FROM pg_catalog.pg_auth_members
  WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='{CAPABILITY}')),
 (SELECT count(DISTINCT m.tenant_id)=1 AND count(*)=1
  FROM public.empire_crm_tenant_memberships AS m
  JOIN public.empire_crm_login_credentials AS c ON c.subject=m.subject
  WHERE {OWNER_WHERE}),
 (SELECT count(*)=0 FROM public.empire_predictive_source_rights_candidate_held),
 (SELECT count(*)=0 FROM public.empire_predictive_source_revocations_held);"""

def preflight()->dict:
    s=source_packet()
    pol=policy_evidence()
    vals=psql(PREFLIGHT).split("|")
    if len(vals)!=12 or any(x not in ("t","f") for x in vals):
        raise RuntimeError("genuine_crm_owner_source_gate_preflight_ambiguous")
    return dict(ready=all(x=="t" for x in vals),
                preflight_flags=[x=="t" for x in vals],
                source_evidence_digest=s["source_digest"],
                official_rights_policy_digest=pol["rights_document_digest"],
                actual_tenant_id_exposed=False,
                rights_owner_attested=False,
                intended_state="PENDING_HELD",
                production_changes=False)

def transaction(source:dict,policy:dict,password:str,*,db:str="empiredb")->str:
    if not password.isalnum() or len(password)!=64:
        raise RuntimeError("generated_credentials_invalid")
    # Bind by SELECT from the genuine canonical CRM OWNER rows; NEVER by
    # a tenant UUID supplied in a JSON packet, CLI flag or web request.
    when=source["observed_at"]
    if not (len(when)<=40 and all(c in "0123456789-:+T." for c in when)):
        raise RuntimeError("source_time_untrusted")
    digest=source["source_digest"]
    rights=policy["rights_document_digest"]
    if len(digest)!=64 or len(rights)!=64:
        raise RuntimeError("source_or_policy_digest_invalid")
    expires=(datetime.now(timezone.utc)+timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return f"""BEGIN;
SET LOCAL statement_timeout='12s';
SET LOCAL lock_timeout='3s';
DO $gate$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v4_outbox_fixture')
   OR pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held') IS NULL
   OR pg_catalog.to_regprocedure('public.read_empire_predictive_source_rights_held(uuid,text,text)') IS NULL
   OR pg_catalog.to_regrole('{LOGIN}') IS NOT NULL
   OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='{CAPABILITY}' AND NOT rolcanlogin
         AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
   OR (SELECT count(DISTINCT m.tenant_id) FROM public.empire_crm_tenant_memberships m
       JOIN public.empire_crm_login_credentials c ON c.subject=m.subject
       WHERE {OWNER_WHERE}) <> 1
   OR (SELECT count(*) FROM public.empire_crm_tenant_memberships m
       JOIN public.empire_crm_login_credentials c ON c.subject=m.subject
       WHERE {OWNER_WHERE}) <> 1
   OR EXISTS(SELECT 1 FROM public.empire_predictive_source_rights_candidate_held)
 THEN RAISE EXCEPTION 'V410_REAL_CRM_OWNER_SOURCE_BINDING_PREFLIGHT_HELD'; END IF;
END;$gate$;
CREATE ROLE {LOGIN} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOBYPASSRLS NOREPLICATION CONNECTION LIMIT 2
  PASSWORD '{password}' VALID UNTIL '{expires}';
ALTER ROLE {LOGIN} SET statement_timeout='3000ms';
ALTER ROLE {LOGIN} SET idle_in_transaction_session_timeout='4000ms';
GRANT CONNECT ON DATABASE {db} TO {LOGIN};
GRANT USAGE ON SCHEMA public TO {CAPABILITY};
GRANT {CAPABILITY} TO {LOGIN} WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
SET LOCAL ROLE empiredb_migrator;
INSERT INTO public.empire_predictive_source_rights_candidate_held (
 tenant_id,source_evidence_digest,permitted_purpose,rights_document_digest,
 evidence_observed_at,valid_until,source_review_state,execution_authority)
SELECT m.tenant_id,'{digest}','{PURPOSE}','{rights}',
 '{when}'::timestamptz,'{expires}'::timestamptz,'PENDING','none'
FROM public.empire_crm_tenant_memberships AS m
JOIN public.empire_crm_login_credentials AS c ON c.subject=m.subject
WHERE {OWNER_WHERE};
DO $count$
BEGIN
 IF (SELECT count(*) FROM public.empire_predictive_source_rights_candidate_held)<>1
 THEN RAISE EXCEPTION 'V410_CRM_SOURCE_BINDING_NOT_SINGLE';END IF;
END;$count$;
COMMIT;"""

def backup()->dict:
    if BACKUP.is_symlink() or BACKUP.exists():
        raise RuntimeError("release_backup_destination_already_present")
    if not BACKUP.parent.is_dir() or BACKUP.parent.is_symlink():
        raise RuntimeError("backup_owner_root_missing")
    BACKUP.mkdir(mode=0o700)
    os.chmod(BACKUP,0o700)
    result={}
    for name,cmd in (
        ("empiredb-pre-bind.dump",["runuser","-u","postgres","--","pg_dump",
                                    "-Fc","-d","empiredb"]),
        ("postgres-globals-pre-bind.sql",["runuser","-u","postgres","--",
                                          "pg_dumpall","--globals-only"])):
        path=BACKUP/name
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as f:
            p=subprocess.run(cmd,stdout=f,stderr=subprocess.PIPE,timeout=120)
            f.flush();os.fsync(f.fileno())
        if p.returncode or path.stat().st_size<1000:
            raise RuntimeError("pre_bind_backup_or_global_roles_export_failed")
        result[name]={"bytes":path.stat().st_size,"sha256":sha(path.read_bytes())}
    check=subprocess.run(["pg_restore","--list",str(BACKUP/"empiredb-pre-bind.dump")],
                         capture_output=True,timeout=20)
    if check.returncode or b"TABLE" not in check.stdout:
        raise RuntimeError("pre_bind_archive_catalog_invalid")
    return result

def apply()->dict:
    if os.geteuid()!=0:
        raise RuntimeError("original_founder_root_owner_required")
    pre=preflight()
    if not pre["ready"]:
        raise RuntimeError("original_crm_rights_preflight_held")
    source=source_packet()
    policy=policy_evidence()
    if policy["rights_document_digest"]!=pre["official_rights_policy_digest"]:
        raise RuntimeError("official_policy_changed_between_approval_checks")
    import psycopg
    from psycopg.conninfo import make_conninfo
    from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
    backups=backup()
    fresh=preflight()
    if (not fresh["ready"]
        or fresh["source_evidence_digest"]!=source["source_digest"]
        or fresh["official_rights_policy_digest"]!=policy["rights_document_digest"]):
        raise RuntimeError("original_crm_or_public_source_rights_changed_after_backup")
    password=secrets.token_hex(32)
    dsn=make_conninfo(host="127.0.0.1",port=5432,dbname="empiredb",user=LOGIN,
                      password=password,connect_timeout=5,sslmode="disable")
    # Stage credentials BEFORE committing the DB role; retain in 0600 root-only
    # custody if the post-commit canary ever fails.
    pending=BACKUP/"pending_rights_reader_dsn"
    fd=os.open(pending,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        f.write(dsn+"\n");f.flush();os.fsync(f.fileno())
    sql=transaction(source,policy,password)
    run=subprocess.run(["runuser","-u","postgres","--","psql","-Xq",
                        "-w","-v","ON_ERROR_STOP=1","-d","empiredb"],
                       input=sql,text=True,capture_output=True,timeout=25)
    if run.returncode:
        raise RuntimeError("held_research_binding_transaction_failed_manual_review_required")
    # The query derives the genuine tenant from canonical active original CRM
    # membership; no real user password, bearer token or tenant ID is logged.
    tenant_sql=f"""SELECT m.tenant_id FROM public.empire_crm_tenant_memberships m
    JOIN public.empire_crm_login_credentials c ON c.subject=m.subject
    WHERE {OWNER_WHERE}"""
    tenant=psql(tenant_sql)
    if str(UUID(tenant))!=tenant:
        raise RuntimeError("postcommit_genuine_crm_tenant_not_canonical")
    reader=EmpireDbHeldSourceRightsReader(dsn)
    match=reader(tenant,source["source_digest"])
    other=reader(str(UUID(int=UUID(tenant).int ^ 1)),source["source_digest"])
    wrong=reader(tenant,"f"*64)
    if (match is None or match.decision!="PENDING_HELD"
        or match.tenant_id!=tenant or match.revoked
        or match.source_admission_authorized or match.real_rights_independently_verified
        or other is None or other.decision!="NO_SOURCE_RIGHTS_HELD"
        or wrong is None or wrong.decision!="NO_SOURCE_RIGHTS_HELD"):
        raise RuntimeError("original_restricted_login_production_canary_failed")
    # Confirm logged-in reader has no direct table access or finance/write
    # capability, despite scoped EXECUTE on the original held read function.
    with psycopg.connect(dsn) as con:
        with con.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            row=cur.execute("""SELECT session_user,
             has_function_privilege(current_user,
             'public.read_empire_predictive_source_rights_held(uuid,text,text)','EXECUTE'),
             has_table_privilege(current_user,
             'public.empire_predictive_source_rights_candidate_held','SELECT'),
             has_table_privilege(current_user,
             'public.empire_predictive_source_rights_candidate_held','INSERT'),
             has_table_privilege(current_user,
             'public.empire_predictive_source_revocations_held','INSERT')""").fetchone()
            if row!=(LOGIN,True,False,False,False):
                raise RuntimeError("original_rights_reader_acl_verification_failed")
    os.replace(pending,DSN_PATH)
    receipt=dict(result="ORIGINAL_CRM_TENANT_SOURCE_RIGHTS_PENDING_HELD_BOUND",
                 observed_at_utc=datetime.now(timezone.utc).isoformat(),
                 actual_crm_tenant_sha256=sha(tenant.encode()),
                 original_ich_source_digest=source["source_digest"],
                 rights_policy_url=POLICY,
                 rights_policy_sha256=policy["rights_document_digest"],
                 rights_public_register_reuse_policy_verified=True,
                 independent_signed_legal_attestation=False,
                 source_review_state="PENDING",
                 cross_tenant_rejected=True,source_mismatch_rejected=True,
                 same_tenant_read="PENDING_HELD",
                 original_restricted_reader_reused=True,
                 restricted_credentials_root_only=True,
                 founder_research_only=True,
                 source_admission_authorized=False,
                 customer_forecast_verified=False,
                 external_redistribution_authorized=False,
                 no_api_service_change=True,
                 backup_files=backups)
    fd=os.open(RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(receipt,f,sort_keys=True,indent=2);f.write("\n")
        f.flush();os.fsync(f.fileno())
    # No tenant ID, password or DSN ever emitted as a tool result.
    return {k:v for k,v in receipt.items() if k not in ("backup_files",)}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight-read-only",action="store_true")
    modes.add_argument("--apply-founder-approved-private-research-only",action="store_true")
    args=parser.parse_args()
    print(json.dumps(preflight() if args.preflight_read_only else apply(),sort_keys=True))
