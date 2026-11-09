"""Independent, disposable PG18 rehearsal of the source HELD binding SQL.

Creates only synthetic company and tenant fixture data in pg_virtualenv.
Never accesses production PG, credentials, CRM users or data providers.
"""
from __future__ import annotations

from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
BIND=ROOT/"scripts/bind_official_ich_to_original_crm_tenant_held_20261108.py"
PREVIOUS=ROOT/"scripts/activate_existing_predictive_066_held_20261108.py"

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

def sql(query,*,db="empire_v4_outbox_fixture",silent=False,allow_failure=False):
    p=subprocess.run(["psql","-XAt","-w","-v","ON_ERROR_STOP=1","-d",db],
       input=query,text=True,capture_output=True,timeout=35)
    if p.returncode and not allow_failure:
        raise RuntimeError("disposable_pg18_rehearsal_sql_failed")
    return (p.returncode,p.stdout.strip())

def run():
    if os.geteuid()==0 or os.environ.get("PGHOST")!="localhost":
        raise RuntimeError("isolated_pg_virtualenv_only")
    port=int(os.environ.get("PGPORT","0"))
    if port <5433:raise RuntimeError("not_disposable_pg_port")
    _,datadir=sql("SHOW data_directory;",db="postgres")
    if not datadir.startswith("/tmp/pg_virtualenv.") or not datadir.endswith("/data/18/regress"):
        raise RuntimeError("not_ephemeral_pg18")
    original=module("original_066_rehearsal",PREVIOUS)
    owner=module("current_066_tenant_bind",BIND)
    _,_=sql("""CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                  NOINHERIT NOBYPASSRLS;
               CREATE ROLE empiredb_migrator_login LOGIN INHERIT NOSUPERUSER
                  NOCREATEDB NOCREATEROLE NOBYPASSRLS;
               GRANT empiredb_migrator TO empiredb_migrator_login
                  WITH INHERIT TRUE, SET TRUE, ADMIN FALSE;""",db="postgres")
    r=subprocess.run(["createdb","-E","UTF8","-T","template0","empire_v4_outbox_fixture"],
                     capture_output=True,timeout=12)
    if r.returncode:raise RuntimeError("disposable_database_unavailable")
    sql("GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator")
    sql(original.original_sql())
    synthetic_tenant="00000000-0000-0000-0000-000000000101"
    sql(f"""BEGIN;
    SET LOCAL ROLE empiredb_migrator;
    CREATE TABLE public.empire_crm_tenant_memberships(
      tenant_id uuid NOT NULL,
      subject text NOT NULL,
      role text NOT NULL,
      status text NOT NULL,
      revoked_at timestamptz,
      verified_at timestamptz NOT NULL,
      valid_until timestamptz,
      evidence_ref text NOT NULL);
    CREATE TABLE public.empire_crm_login_credentials(
      subject text NOT NULL,
      invitation_tenant_id uuid NOT NULL,
      status text NOT NULL,
      password_change_required boolean NOT NULL,
      invitation_redeemed_at timestamptz,
      verified_at timestamptz NOT NULL,
      evidence_ref text NOT NULL);
    INSERT INTO public.empire_crm_tenant_memberships
      (tenant_id,subject,role,status,verified_at,evidence_ref)
       VALUES ('{synthetic_tenant}','fixture-founder','owner','active',
               CURRENT_TIMESTAMP-INTERVAL '1 day','synthetic_fixture');
    INSERT INTO public.empire_crm_login_credentials
      (subject,invitation_tenant_id,status,password_change_required,
       invitation_redeemed_at,verified_at,evidence_ref)
       VALUES ('fixture-founder','{synthetic_tenant}','active',false,
               CURRENT_TIMESTAMP-INTERVAL '1 hour',
               CURRENT_TIMESTAMP-INTERVAL '1 day','synthetic_fixture');
    COMMIT;""")
    fake_source=dict(source_digest="a"*64,
                     observed_at=(datetime.now(timezone.utc)).isoformat())
    fake_policy=dict(rights_document_digest="b"*64)
    password="c"*64
    code=owner.transaction(fake_source,fake_policy,password,db="empire_v4_outbox_fixture")
    # A second independently active CRM owner tenant must make the entire
    # binding transaction fail before any login, role grant or row is created.
    other_tenant="00000000-0000-0000-0000-000000000102"
    sql(f"""BEGIN;SET LOCAL ROLE empiredb_migrator;
        INSERT INTO public.empire_crm_tenant_memberships
         (tenant_id,subject,role,status,verified_at,evidence_ref)
        VALUES ('{other_tenant}','second-owner','owner','active',
                CURRENT_TIMESTAMP-INTERVAL '1 day','synthetic_fixture');
        INSERT INTO public.empire_crm_login_credentials
         (subject,invitation_tenant_id,status,password_change_required,
          invitation_redeemed_at,verified_at,evidence_ref)
        VALUES ('second-owner','{other_tenant}','active',false,
                CURRENT_TIMESTAMP-INTERVAL '1 hour',
                CURRENT_TIMESTAMP-INTERVAL '1 day','synthetic_fixture');
        COMMIT;""")
    ambiguous,_=sql(code,allow_failure=True)
    if ambiguous==0:
        raise RuntimeError("ambiguous_credentialled_owner_allowed_to_bind")
    _,no_changes=sql("""SELECT
       (SELECT count(*)=0 FROM pg_catalog.pg_roles
        WHERE rolname='empire_predictive_rights_login'),
       (SELECT count(*)=0 FROM public.empire_predictive_source_rights_candidate_held)""")
    if no_changes!="t|t":
        raise RuntimeError("ambiguous_owner_transaction_not_atomic")
    sql("""BEGIN;SET LOCAL ROLE empiredb_migrator;
        DELETE FROM public.empire_crm_login_credentials WHERE subject='second-owner';
        DELETE FROM public.empire_crm_tenant_memberships WHERE subject='second-owner';
        COMMIT;""")
    rc,_=sql(code)
    if rc:raise RuntimeError("synthetic_original_source_bind_failed")
    _,rows=sql("""SELECT count(*), min(source_review_state), min(execution_authority)
           FROM public.empire_predictive_source_rights_candidate_held""")
    if rows!="1|PENDING|none":
        raise RuntimeError("synthetic_research_held_record_not_proven")
    # Test exact real source reader class against synthetic connection and
    # actual original database function, not replacement code.
    from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
    from psycopg.conninfo import make_conninfo
    dsn=make_conninfo(host="localhost",port=port,
           dbname="empire_v4_outbox_fixture",user=owner.LOGIN,password=password,
           connect_timeout=4)
    reader=EmpireDbHeldSourceRightsReader(dsn)
    result=reader(synthetic_tenant,fake_source["source_digest"])
    if result is None or result.decision!="PENDING_HELD" or result.execution_authority!="none":
        raise RuntimeError("synthetic_real_066_reader_not_pending_held")
    mismatch=reader(str(UUID(int=UUID(synthetic_tenant).int ^ 1)),
                    fake_source["source_digest"])
    if mismatch is None or mismatch.decision!="NO_SOURCE_RIGHTS_HELD":
        raise RuntimeError("synthetic_cross_tenant_rights_not_denied")
    import psycopg
    with psycopg.connect(dsn) as con:
        with con.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            row=cur.execute("""SELECT session_user,
             has_function_privilege(current_user,
              'public.read_empire_predictive_source_rights_held(uuid,text,text)','EXECUTE'),
             has_table_privilege(current_user,
              'public.empire_predictive_source_rights_candidate_held','SELECT'),
             has_table_privilege(current_user,
              'public.empire_predictive_source_rights_candidate_held','INSERT')""").fetchone()
            if row!=(owner.LOGIN,True,False,False):
                raise RuntimeError("synthetic_original_066_dedicated_reader_acl_incorrect")
    # Append-only revocation is tested on only synthetic, disposable DB.
    sql(f"""BEGIN;
        SET LOCAL ROLE empiredb_migrator;
        INSERT INTO public.empire_predictive_source_revocations_held
        (tenant_id,source_evidence_digest,permitted_purpose,reason_digest)
        VALUES ('{synthetic_tenant}','{'a'*64}',
        'PRIVATE_PREDICTIVE_RESEARCH_ONLY','{'e'*64}');
        COMMIT;""")
    revoked=reader(synthetic_tenant,fake_source["source_digest"])
    if revoked is None or revoked.decision!="REVOKED_HELD" or not revoked.revoked:
        raise RuntimeError("synthetic_original_revocation_not_terminal")
    # The original one-row source proof must never give customer authority.
    return {"result":"ORIGINAL_066_CRM_SOURCE_BIND_DISPOSABLE_PG18_PASS",
       "reader_decision":"PENDING_HELD","cross_tenant":"NO_SOURCE_RIGHTS_HELD",
       "revocation":"REVOKED_HELD","direct_table_access":False,
       "new_service":False,"production_changes":False,
       "customer_delivery_authorized":False}

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
