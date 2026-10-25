"""V4.18 opportunity-denominator authority, transition, math and PG18 tests."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import json,os,runpy,shutil,subprocess
import pytest

from empire_os.predictive_revenue_v418_opportunities import (
    SCHEMA,review_v418_opportunity_custody_held,
)

ROOT=Path(__file__).resolve().parents[1]
SQL_FILE=ROOT/"migrations/empiredb/070_predictive_revenue_gtm_opportunity_custody_held.sql"
SCRIPT=ROOT/"scripts/rehearse_predictive_revenue_v418_opportunities_20261025.sh"
V415=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v415_direct_cash_reader_20261025.py"))
SIGNED=V415["signed"]
TWIN=V415["twin"]
TENANT=V415["TENANT"]
OTHER=V415["OTHER"]
NOW=datetime.now(timezone.utc)
GOOD=(7,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,False,False,False)


class Cursor:
    def __init__(self,rows,identity=("empire_predictive_cash_candidate_login","empire_predictive_cash_candidate_reader")):
        self.rows=rows; self.identity=identity; self.statements=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):self.statements.append((sql,params))
    def fetchone(self):return self.identity
    def fetchall(self):return self.rows


class Connection:
    def __init__(self,cur):self.cur=cur
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cur


def invoke(*,rows=None,identity=None,model=None,auth=None,token=None,
           start=None,end=None,dsn="dummy-owner-dsn",connect=None):
    cur=Cursor([GOOD] if rows is None else rows,
               identity or ("empire_predictive_cash_candidate_login",
                            "empire_predictive_cash_candidate_reader"))
    if auth is None:
        auth,valid=SIGNED()
        if token is None:token=valid
    if connect is None:connect=lambda dsn,**kwargs:Connection(cur)
    result=review_v418_opportunity_custody_held(
        research_twin=TWIN() if model is None else model,
        signed_crm_bearer=token,crm_verifier=auth,
        window_start=NOW-timedelta(days=14) if start is None else start,
        window_end=NOW-timedelta(days=1) if end is None else end,
        dedicated_cash_dsn=dsn,connect_factory=connect,
    )
    return result,cur


def test_v418_mock_source_cannot_claim_actual_cvr_or_ecac():
    result,cur=invoke()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="V418_INJECTED_CONNECTOR_NOT_INDEPENDENT_EVIDENCE_HELD"
    assert result["custody_claimed_opportunity_count"] is None
    assert result["research_cvr_all_opportunities_pct"] is None
    assert result["research_ecac_minor_per_buyer_order"] is None
    assert result["verified_30_60_90_cash_forecasts"] is None
    assert result["maturation_factors_are_illustrative_only"]==("0.45","0.80","1.00")
    assert result["paid_traffic_budget_minor"]==0
    assert result["execution_authority"]=="none"
    assert cur.statements[0][0]=="SET TRANSACTION READ ONLY"
    assert cur.statements[2][0]=="SET LOCAL ROLE empire_predictive_cash_candidate_reader"
    assert cur.statements[4][1][0]==TENANT


@pytest.mark.parametrize("row",[
    (7,2,1,1,2,2,0,0,Decimal(700),1,"USD",False,False,False,False),
    (7,2,1,1,2,2,1,1,Decimal(700),1,"USD",False,False,False,False),
    (7,2,1,1,2,2,1,0,Decimal(-5),1,"USD",False,False,False,False),
    (7,2,1,1,2,2,1,0,Decimal(700),2,"USD",False,False,False,False),
    (7,2,1,1,2,2,1,0,Decimal(700),1,"GBP",False,False,False,False),
    (7,2,1,1,2,2,1,0,Decimal(700),1,"USD",True,False,False,False),
    (7,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,True,False,False),
    (7,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,False,True,False),
    (7,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,False,False,True),
    (True,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,False,False,False),
    (5001,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,False,False,False),
    (7,2,1,1,2,2,1,0,Decimal(700),1,"USD",False,False,False),
])
def test_v418_untrusted_counts_forecast_flags_or_currencies_rejected(row):
    result,_=invoke(rows=[row])
    assert result["status"] not in ("V418_BOUNDED_TENANT_CUSTODY_COHORT_ONLY_HELD",)
    assert result["custody_claimed_opportunity_count"] is None
    assert result["funds_movement_authorized"] is False


def test_v418_absent_result_not_a_zero_cohort():
    result,_=invoke(rows=[])
    assert result["status"]=="V418_CUSTODY_COHORT_RESULT_MISSING_HELD"
    assert result["custody_claimed_opportunity_count"] is None


@pytest.mark.parametrize("start,end",[
    (NOW-timedelta(days=40),NOW-timedelta(days=1)),
    (NOW-timedelta(days=1),NOW+timedelta(days=1)),
    (NOW-timedelta(days=1),NOW-timedelta(days=1)),
])
def test_v418_window_limits(start,end):
    with pytest.raises(ValueError,match="BOUNDED_WINDOW"):
        invoke(start=start,end=end)


def test_v418_denies_wrong_membership_or_tenant_model():
    bad=TWIN()
    bad["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_MISMATCH"):
        invoke(model=bad)
    bad=TWIN()
    bad["approved_commercial_forecast"]=True
    with pytest.raises(ValueError,match="NO_EXECUTION_TWIN"):
        invoke(model=bad)
    verifier,token=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_CRM"):
        invoke(auth=verifier,token=token+"corrupt")


def test_v418_restricted_login_and_missing_schema_are_held():
    result,_=invoke(identity=("postgres","empire_predictive_cash_candidate_reader"))
    assert result["status"]=="V418_RESTRICTED_SESSION_IDENTITY_INVALID_HELD"
    def unavailable(*args,**kwargs):raise RuntimeError("secret owner credentials")
    result,_=invoke(connect=unavailable)
    assert result["status"]=="V418_RESTRICTED_CUSTODY_READER_UNAVAILABLE_HELD"
    assert "secret" not in str(result)


def test_v418_prepared_sql_uses_original_gtm_and_enforces_states():
    sql=SQL_FILE.read_text()
    assert "PREPARED/HELD ONLY" in sql
    assert "REFERENCES public.gtm_opportunities(id)" in sql
    assert "REFERENCES public.empire_predictive_opportunity_custody_v418(opportunity_id)" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "V418_FIRST_STATE_MUST_BE_OPEN" in sql
    assert "V418_INVALID_TERMINAL_TRANSITION" in sql
    assert "V418_CROSS_TENANT_OR_MISSING_CONVERSION_ORDER" in sql
    assert "V418_APPEND_ONLY_CUSTODY_EVENTS" in sql
    assert "V418_SESSION_TENANT_REQUIRED" in sql
    assert "V418_BOUNDED_WINDOW_REQUIRED" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')" in sql
    assert "CREATE DATABASE" not in sql and "CREATE ROLE " not in sql


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="disposable PostgreSQL18 unavailable")
def test_v418_real_ephemeral_postgres18_tenant_denominator_and_transitions():
    process=subprocess.run(["pg_virtualenv","-t","bash",str(SCRIPT)],
       cwd=ROOT,text=True,capture_output=True,timeout=120)
    assert process.returncode==0,(process.stdout+process.stderr)[-2500:]
    objs=[json.loads(line) for line in process.stdout.splitlines()
          if line.startswith("{")]
    assert len(objs)==1
    assert objs[0]["status"]=="V418_EPHEMERAL_OPPORTUNITY_CUSTODY_PASS"
    assert objs[0]["pg18_isolated"] is True
    assert objs[0]["production_db_writes"] is False
    assert objs[0]["live_payments_enabled"] is False
    assert "Dropping cluster 18/regress" in process.stdout+process.stderr


def test_v418_disposable_rehearsal_refuses_production_port():
    process=subprocess.run(["bash",str(SCRIPT)],cwd=ROOT,
       env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
       text=True,capture_output=True,timeout=8)
    assert process.returncode!=0
    assert "V418_EPHEMERAL_OPPORTUNITY_CUSTODY_PASS" not in process.stdout


def test_v418_no_money_paid_marketing_or_new_api_in_adapter():
    src=(ROOT/"empire_os/predictive_revenue_v418_opportunities.py").read_text()
    for name in ("commit(", "execute_payment(", "execute_trade(",
                 "send_email(", "CREATE TABLE", "create_engine(",
                 "redis.Redis(", "systemctl", "router.post(", "model.fit("):
        assert name not in src
