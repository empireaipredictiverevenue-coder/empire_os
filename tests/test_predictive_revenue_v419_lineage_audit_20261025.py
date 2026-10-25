"""V4.19 original GTM source metadata vs V4.18 same-snapshot tests."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import json,os,runpy,shutil,subprocess
import pytest

from empire_os.predictive_revenue_v419_lineage_audit import (
    SCHEMA,review_v419_source_lineage_held,
)

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/071_predictive_revenue_source_lineage_audit_held.sql"
SCRIPT=ROOT/"scripts/rehearse_predictive_revenue_v419_lineage_20261025.sh"
OLDER=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v418_opportunities_20261025.py"))
SIGNED=OLDER["SIGNED"]
TWIN=OLDER["TWIN"]
TENANT=OLDER["TENANT"]
OTHER=OLDER["OTHER"]
GOOD=OLDER["GOOD"]
NOW=datetime.now(timezone.utc)
LINEAGE=(7,7,1,1,1,1,0,1,1,2,2,2,False,False,False,False,False)


class Cursor:
    def __init__(self,older,newer,identity=(
            "empire_predictive_cash_candidate_login",
            "empire_predictive_cash_candidate_reader")):
        self.old=older
        self.new=newer
        self.identity=identity
        self.statements=[]
        self.query=0
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,sql,args=None):
        self.statements.append((sql,args))
        if sql.startswith("SELECT custody_count"):self.query=1
        if sql.startswith("SELECT selected_custody_claim_count"):self.query=2
    def fetchone(self):return self.identity
    def fetchall(self):return self.old if self.query==1 else self.new


class Connection:
    def __init__(self,cursor):self.cur=cursor
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return self.cur


def invoke(*,v418=None,lineage=None,identity=None,model=None,token=None,verifier=None,
           start=None,end=None,connector=None):
    cursor=Cursor([GOOD] if v418 is None else v418,
                  [LINEAGE] if lineage is None else lineage,
                  identity=identity or (
                      "empire_predictive_cash_candidate_login",
                      "empire_predictive_cash_candidate_reader",
                  ))
    if verifier is None:
        verifier,bearer=SIGNED()
        if token is None:token=bearer
    if connector is None:
        connector=lambda dsn,**kwargs:Connection(cursor)
    report=review_v419_source_lineage_held(
        research_twin=TWIN() if model is None else model,
        signed_crm_bearer=token,
        crm_verifier=verifier,
        window_start=NOW-timedelta(days=14) if start is None else start,
        window_end=NOW-timedelta(days=1) if end is None else end,
        dedicated_cash_dsn="fixture-owner-dsn",
        connect_factory=connector,
    )
    return report,cursor


def test_v419_test_injected_provenance_not_promoted():
    report,cur=invoke()
    assert report["schema_version"]==SCHEMA
    assert report["status"]=="V419_INJECTED_CONNECTOR_NOT_EVIDENCE_HELD"
    assert report["custody_claimed"] is None
    assert report["source_rights_independently_verified"] is False
    assert report["upstream_opportunity_intake_complete"] is False
    assert report["customer_cvr_verified"] is False
    assert report["customer_ecac_verified"] is False
    assert report["cash_revenue_verified_minor"] is None
    assert report["execution_authority"]=="none"
    assert cur.statements[0][0]=="SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert cur.statements[2][0]=="SET LOCAL ROLE empire_predictive_cash_candidate_reader"
    assert cur.statements[4][1]==cur.statements[5][1]
    assert cur.statements[4][1][0]==TENANT


@pytest.mark.parametrize("row",[
    (8,7,1,1,1,1,0,1,1,2,2,2,False,False,False,False,False),
    (7,6,1,1,1,1,0,1,1,2,2,2,False,False,False,False,False),
    (7,7,8,1,1,1,0,1,1,2,2,2,False,False,False,False,False),
    (7,7,-1,1,1,1,0,1,1,2,2,2,False,False,False,False,False),
    (7,7,1,1,1,1,0,0,1,2,2,2,False,False,False,False,False),
    (7,7,1,1,1,1,0,1,0,2,2,2,False,False,False,False,False),
    (7,7,1,1,1,1,0,1,1,2,2,2,True,False,False,False,False),
    (7,7,1,1,1,1,0,1,1,2,2,2,False,True,False,False,False),
    (7,7,1,1,1,1,0,1,1,2,2,2,False,False,True,False,False),
    (7,7,1,1,1,1,0,1,1,2,2,2,False,False,False,True,False),
    (7,7,1,1,1,1,0,1,1,2,2,2,False,False,False,False,True),
    (7,7,1,1,1,1,0,1,1,2,2,2,False,False,False,False),
    (True,7,1,1,1,1,0,1,1,2,2,2,False,False,False,False,False),
])
def test_v419_forged_lineage_and_authority_fail_closed(row):
    report,_=invoke(lineage=[row])
    assert report["status"]!="V419_ORIGINAL_GTM_METADATA_AUDITED_HELD"
    assert report["custody_claimed"] is None
    assert report["source_ingestion_authorized"] is False


def test_v419_snapshot_omission_cannot_become_zero_population():
    report,_=invoke(lineage=[])
    assert report["status"]=="V419_INCOMPLETE_COHORT_COMPARISON_HELD"
    assert report["custody_claimed"] is None
    report,_=invoke(v418=[])
    assert report["status"]=="V419_INCOMPLETE_COHORT_COMPARISON_HELD"
    assert report["original_gtm_matches"] is None


def test_v419_existing_v418_forged_currency_cannot_match():
    changed=list(GOOD)
    changed[10]="GBP"
    report,_=invoke(v418=[tuple(changed)])
    assert report["status"]=="V419_V418_COMPARISON_NOT_TRUSTED_HELD"


@pytest.mark.parametrize("start,end",[
    (NOW-timedelta(days=40),NOW-timedelta(days=1)),
    (NOW-timedelta(days=1),NOW+timedelta(days=1)),
    (NOW-timedelta(days=1),NOW-timedelta(days=1)),
])
def test_v419_reject_unbounded_or_future_window(start,end):
    with pytest.raises(ValueError,match="BOUNDED_WINDOW"):
        invoke(start=start,end=end)


def test_v419_signatures_tenant_read_role_and_dsn_fail_closed():
    changed=TWIN();changed["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_BOUNDARY"):
        invoke(model=changed)
    verifier,token=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_CRM_MEMBERSHIP"):
        invoke(verifier=verifier,token=token+"tamper")
    report,_=invoke(identity=("postgres","empire_predictive_cash_candidate_reader"))
    assert report["status"]=="V419_READER_IDENTITY_INVALID_HELD"
    def fail(*args,**kwargs):raise ValueError("sensitive password")
    report,_=invoke(connector=fail)
    assert report["status"]=="V419_READER_UNAVAILABLE_HELD"
    assert "password" not in str(report)


def test_v419_held_sql_uses_existing_original_gtm_and_only_function_grants():
    sql=MIGRATION.read_text()
    assert "HELD/NO PRODUCTION APPLY" in sql
    assert "V419_V418_AND_ORIGINAL_GTM_REQUIRED" in sql
    assert "public.gtm_opportunities g" in sql
    assert "public.empire_predictive_opportunity_custody_v418 c" in sql
    assert "v_session_tenant := public.empire_current_tenant_id()" in sql
    assert "session_user<>'empire_predictive_cash_candidate_login'" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "source_licence_verified" in sql
    assert "false,false,false,false,false" in sql
    for forbidden in ("CREATE DATABASE ","CREATE ROLE ","CREATE TABLE "):
        assert forbidden not in sql


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="isolated PG18 missing")
def test_v419_real_isolated_pg18_source_metadata_snapshot():
    result=subprocess.run(["pg_virtualenv","-t","bash",str(SCRIPT)],
        cwd=ROOT,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,(result.stdout+result.stderr)[-2000:]
    receipts=[json.loads(line) for line in result.stdout.splitlines()
              if line.startswith("{")]
    assert len(receipts)==1
    assert receipts[0]["status"]=="V419_EPHEMERAL_SOURCE_LINEAGE_PASS"
    assert receipts[0]["pg18_isolated"] is True
    assert receipts[0]["production_db_writes"] is False
    assert "Dropping cluster 18/regress" in result.stdout+result.stderr


def test_v419_ephemeral_fixture_cannot_run_on_live_port():
    result=subprocess.run(["bash",str(SCRIPT)],cwd=ROOT,
        env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
        text=True,capture_output=True,timeout=8)
    assert result.returncode != 0
    assert "V419_EPHEMERAL_SOURCE_LINEAGE_PASS" not in result.stdout
