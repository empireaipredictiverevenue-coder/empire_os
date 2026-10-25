"""V4.20 original tenant three-pillar claims, tier and settlement holds."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import json,os,runpy,shutil,subprocess

import pytest

from empire_os.predictive_revenue_v420_three_pillar_audit import (
    SCHEMA,review_v420_three_pillar_held,
)

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/072_predictive_revenue_three_pillar_claims_held.sql"
SCRIPT=ROOT/"scripts/rehearse_predictive_revenue_v420_three_pillar_20261025.sh"
V418=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v418_opportunities_20261025.py"))
SIGNED=V418["SIGNED"]
TWIN=V418["TWIN"]
TENANT=V418["TENANT"]
OTHER=V418["OTHER"]
NOW=datetime.now(timezone.utc)
ORIGINAL_LINEAGE=(7,7,1,1,1,1,0,1,1,2,2,2,False,False,False,False,False)
THREE_PILLAR=(6,6,6,3,3,3,1,1,Decimal(600),5000,
              False,False,False,False,False,False)


class Cursor:
    def __init__(self,old,new,identity=(
        "empire_predictive_cash_candidate_login","empire_predictive_cash_candidate_reader",
    )):
        self.old=old;self.new=new;self.identity=identity;self.called=0;self.queries=[]
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,sql,params=None):
        self.queries.append((sql,params))
        if sql.startswith("SELECT selected_custody_claim_count"):self.called=1
        if sql.startswith("SELECT opportunity_count"):self.called=2
    def fetchone(self):return self.identity
    def fetchall(self):return self.old if self.called==1 else self.new


class Conn:
    def __init__(self,cur):self.cur=cur
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return self.cur


def invoke(*,v419=None,v420=None,identity=None,channel="organic",
           model=None,verifier=None,token=None,connect=None,
           start=None,end=None):
    cur=Cursor(
        [ORIGINAL_LINEAGE] if v419 is None else v419,
        [THREE_PILLAR] if v420 is None else v420,
        identity or (
            "empire_predictive_cash_candidate_login",
            "empire_predictive_cash_candidate_reader",
        )
    )
    if verifier is None:
        verifier,signed=SIGNED()
        if token is None:token=signed
    if connect is None:connect=lambda dsn,**kwargs:Conn(cur)
    result=review_v420_three_pillar_held(
        research_twin=TWIN() if model is None else model,
        signed_crm_bearer=token,crm_verifier=verifier,
        channel_name=channel,
        window_start=NOW-timedelta(days=14) if start is None else start,
        window_end=NOW-timedelta(days=1) if end is None else end,
        dedicated_cash_dsn="fixture-only-credentials",
        connect_factory=connect,
    )
    return result,cur


def test_v420_mock_pillars_never_approve_money_or_qualified_cohorts():
    report,cur=invoke()
    assert report["schema_version"]==SCHEMA
    assert report["status"]=="V420_INJECTED_CONNECTOR_NOT_SOURCE_PROOF_HELD"
    assert report["opportunities_in_claimed_channel"] is None
    assert report["research_readiness_tier"]=="UNVERIFIED"
    assert report["fully_audited_independently_verified"] is False
    assert report["verified_cvr_ecac_authorized"] is False
    assert report["verified_30_60_90_cash_forecasts"] is None
    assert report["economic_memory_write_authorized"] is False
    assert report["funds_movement_authorized"] is False
    assert report["execution_authority"]=="none"
    assert cur.queries[0][0]=="SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert cur.queries[2][0]=="SET LOCAL ROLE empire_predictive_cash_candidate_reader"
    assert cur.queries[4][1]==(TENANT,NOW-timedelta(days=14),NOW-timedelta(days=1)) or cur.queries[4][1][0]==TENANT
    assert cur.queries[5][1][1]=="organic"


@pytest.mark.parametrize("row",[
    (7,6,6,3,3,3,1,1,Decimal(600),5000,False,False,False,False,False,False),
    (6,6,7,3,3,3,1,1,Decimal(600),5000,False,False,False,False,False,False),
    (6,6,6,3,4,3,1,1,Decimal(600),5000,False,False,False,False,False,False),
    (6,6,6,3,3,3,4,1,Decimal(600),5000,False,False,False,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5001,False,False,False,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),9000,False,False,False,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(-1),5000,False,False,False,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,True,False,False,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,False,True,False,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,False,False,True,False,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,False,False,False,True,False,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,False,False,False,False,True,False),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,False,False,False,False,False,True),
    (6,6,6,3,3,3,1,1,Decimal(600),5000,False,False,False,False,False),
])
def test_v420_forged_amounts_rights_claims_and_bad_scores_fail_closed(row):
    report,_=invoke(v420=[row])
    assert report["status"]!="V420_THREE_PILLAR_CLAIMS_ONLY_HELD"
    assert report["opportunities_in_claimed_channel"] is None
    assert report["fully_audited_channel_count"]==0


def test_v420_made_up_full_coverage_does_not_unlock_financial_authority():
    perfect=(6,6,6,6,6,3,3,0,Decimal(600),10000,
             False,False,False,False,False,False)
    report,_=invoke(v420=[perfect])
    assert report["status"]=="V420_INJECTED_CONNECTOR_NOT_SOURCE_PROOF_HELD"
    assert report["fully_audited_independently_verified"] is False
    assert report["fully_audited_channel_count"]==0
    assert report["verified_30_60_90_cash_forecasts"] is None


def test_v420_missing_audit_rows_are_unknown_not_zero():
    report,_=invoke(v420=[])
    assert report["status"]=="V420_MISSING_CONSISTENT_EVIDENCE_ROWS_HELD"
    assert report["opportunities_in_claimed_channel"] is None
    report,_=invoke(v419=[])
    assert report["status"]=="V420_MISSING_CONSISTENT_EVIDENCE_ROWS_HELD"


@pytest.mark.parametrize("channel",["","Organic","organic;select", "0","a"*50,"pay-per-call"])
def test_v420_restrict_arbitrary_channel_identifiers(channel):
    with pytest.raises(ValueError,match="EXACT_BOUNDED_CHANNEL"):
        invoke(channel=channel)


def test_v420_original_crm_tenant_role_and_disconnected_db():
    model=TWIN();model["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_MISMATCH"):
        invoke(model=model)
    verifier,token=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_CRM_MEMBERSHIP"):
        invoke(verifier=verifier,token=token+"invalid")
    report,_=invoke(identity=("postgres","empire_predictive_cash_candidate_reader"))
    assert report["status"]=="V420_ORIGINAL_READER_IDENTITY_INVALID_HELD"
    def unavailable(*args,**kwargs):
        raise RuntimeError("fake password string")
    report,_=invoke(connect=unavailable)
    assert report["status"]=="V420_ORIGINAL_READER_UNAVAILABLE_HELD"
    assert "fake password" not in str(report)


@pytest.mark.parametrize("start,end",[
    (NOW-timedelta(days=40),NOW-timedelta(days=1)),
    (NOW-timedelta(days=1),NOW+timedelta(days=1)),
    (NOW-timedelta(days=1),NOW-timedelta(days=1)),
])
def test_v420_invalid_window_is_rejected(start,end):
    with pytest.raises(ValueError,match="BOUNDED_WINDOW"):
        invoke(start=start,end=end)


def test_v420_prepared_three_pillar_schema_no_duplicate_tenants_or_orders():
    source=MIGRATION.read_text()
    assert "DO NOT apply to production" in source
    assert "CREATE TABLE public.empire_predictive_source_authorization_claims_v420" in source
    assert "CREATE TABLE public.empire_predictive_event_coverage_claims_v420" in source
    assert "CREATE TABLE public.empire_predictive_financial_match_claims_v420" in source
    assert "V420_APPEND_ONLY_CLAIM_HISTORY" in source
    assert "consent_artifact_digest" in source
    assert "publisher_network_scope_digest" in source
    assert "REVOKE ALL ON public.empire_predictive_financial_match_claims_v420" in source
    assert "V420_SOURCE_MUTATION_NOT_BLOCKED" not in source

    assert "FORCE ROW LEVEL SECURITY" in source
    assert "V420_SIGNED_SESSION_TENANT_REQUIRED" in source
    assert "v_total>5000" in source
    assert "GRANT EXECUTE ON FUNCTION" in source
    assert "false,false,false,false,false,false" in source
    for forbidden in ("CREATE DATABASE ","CREATE ROLE ","CREATE TABLE public.empire_orders",
                      "CREATE TABLE public.empire_tenants","CREATE TABLE public.empire_opportunities"):
        assert forbidden not in source


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="disposable PG18 missing")
def test_v420_real_pg18_three_pillar_and_discrepancy_end_to_end():
    result=subprocess.run(["pg_virtualenv","-t","bash",str(SCRIPT)],
       cwd=ROOT,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,(result.stdout+result.stderr)[-2300:]
    receipts=[json.loads(line) for line in result.stdout.splitlines()
              if line.startswith("{")]
    assert len(receipts)==1
    assert receipts[0]["status"]=="V420_EPHEMERAL_THREE_PILLAR_PASS"
    assert receipts[0]["pg18_isolated"] is True
    assert receipts[0]["production_db_writes"] is False
    assert receipts[0]["live_payments_enabled"] is False
    assert "Dropping cluster 18/regress" in result.stdout+result.stderr


def test_v420_pg18_fixture_refuses_production_port():
    result=subprocess.run(["bash",str(SCRIPT)],
        cwd=ROOT,env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
        text=True,capture_output=True,timeout=8)
    assert result.returncode!=0
    assert "V420_EPHEMERAL_THREE_PILLAR_PASS" not in result.stdout
