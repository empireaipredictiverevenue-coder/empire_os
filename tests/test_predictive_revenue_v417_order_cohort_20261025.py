"""V4.17 original CRM-bound full buyer-owned ORDER census tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import runpy
import shutil
import subprocess

import pytest

from empire_os.predictive_revenue_v417_order_cohort import (
    SCHEMA, review_v417_tenant_order_cohort_held,
)

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/069_predictive_revenue_tenant_order_cohort_held.sql"
SCRIPT=ROOT/"scripts/rehearse_predictive_revenue_v417_order_cohort_20261025.sh"
OLD=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v415_direct_cash_reader_20261025.py"))
SIGNED=OLD["signed"]
TWIN=OLD["twin"]
TENANT=OLD["TENANT"]
OTHER=OLD["OTHER"]
NOW=datetime.now(timezone.utc)


class Cursor:
    def __init__(self,rows,identity=(
        "empire_predictive_cash_candidate_login",
        "empire_predictive_cash_candidate_reader",
    )):
        self.rows=rows
        self.identity=identity
        self.statements=[]
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,sql,args=None):self.statements.append((sql,args))
    def fetchone(self):return self.identity
    def fetchall(self):return self.rows


class Connection:
    def __init__(self,cur):self.cur=cur
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return self.cur


GOOD=(7,4,1,1,1,1,5,True,True,False,False,False,False)


def invoke(*,rows=None,identity=None,model=None,auth=None,token=None,
           start=None,end=None,dsn="fixture-owner-secret",connect=None):
    if rows is None:rows=[GOOD]
    cur=Cursor(rows,identity) if identity is not None else Cursor(rows)
    if auth is None:
        auth,valid=SIGNED()
        if token is None:token=valid
    if connect is None:connect=lambda dsn,**_:Connection(cur)
    result=review_v417_tenant_order_cohort_held(
        research_twin=TWIN() if model is None else model,
        signed_crm_bearer=token,crm_verifier=auth,
        window_start=NOW-timedelta(days=14) if start is None else start,
        window_end=NOW-timedelta(days=1) if end is None else end,
        dedicated_cash_dsn=dsn,connect_factory=connect,
    )
    return result,cur


def test_v417_valid_mock_census_must_never_be_independent_financial_proof():
    report,cur=invoke()
    assert report["schema_version"]==SCHEMA
    assert report["status"]=="V417_TEST_CONNECTOR_NOT_CANONICAL_EVIDENCE_HELD"
    assert report["buyer_owned_order_count"] is None
    assert report["gtm_opportunity_denominator_complete"] is False
    assert report["actual_cash_collected_minor_units"] is None
    assert report["execution_authority"]=="none"
    assert cur.statements[0][0]=="SET TRANSACTION READ ONLY"
    assert cur.statements[2][0]=="SET LOCAL ROLE empire_predictive_cash_candidate_reader"
    assert cur.statements[4][1][0]==TENANT


@pytest.mark.parametrize("row",[
    (7,4,1,1,2,1,5,True,True,False,False,False,False),
    (7,4,1,1,1,1,5,False,True,False,False,False,False),
    (7,4,1,1,1,1,6,True,True,False,False,False,False),
    (7,4,1,1,1,8,0,False,True,False,False,False,False),
    (7,4,1,1,1,1,5,True,True,True,False,False,False),
    (7,4,1,1,1,1,5,True,True,False,True,False,False),
    (7,4,1,1,1,1,5,True,True,False,False,True,False),
    (7,4,1,1,1,1,5,True,True,False,False,False,True),
    (7,4,1,1,1,1,5,True,False,False,False,False,False),
    (7,4,1,1,1,1,5,True,True,False,False,False),
    (True,4,1,1,1,1,5,True,True,False,False,False,False),
    (5001,4998,1,1,1,1,5,True,True,False,False,False,False),
    (-1,0,0,0,0,0,0,False,True,False,False,False,False),
])
def test_v417_forged_or_inconsistent_db_counts_fail_closed(row):
    report,_=invoke(rows=[row])
    assert report["status"]!="V417_BOUNDED_TENANT_ORDER_COHORT_ONLY_HELD"
    assert report["buyer_owned_order_count"] is None
    assert report["eligible_for_revenue_forecast_calibration"] is False


def test_v417_missing_results_never_zero_or_complete():
    report,_=invoke(rows=[])
    assert report["status"]=="V417_INCOMPLETE_OR_MALFORMED_COHORT_HELD"
    assert report["buyer_owned_order_count"] is None
    assert report["order_cohort_window_complete_under_buyer_ownership"] is False


@pytest.mark.parametrize("start,end",[
    (NOW-timedelta(days=33),NOW-timedelta(days=1)),
    (NOW+timedelta(days=1),NOW+timedelta(days=2)),
    (NOW-timedelta(days=1),NOW-timedelta(days=1)),
    (NOW-timedelta(days=100),NOW-timedelta(days=130)),
])
def test_v417_unbounded_or_future_cohorts_rejected(start,end):
    with pytest.raises(ValueError,match="BOUNDED_HISTORICAL_WINDOW"):
        invoke(start=start,end=end)


def test_v417_requires_signed_crm_original_tenant():
    wrong=TWIN()
    wrong["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_IDENTITY_MISMATCH"):
        invoke(model=wrong)
    wrong=TWIN()
    wrong["approved_commercial_forecast"]=True
    with pytest.raises(ValueError,match="ORIGINAL_SIMULATION"):
        invoke(model=wrong)
    auth,token=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_CRM"):
        invoke(auth=auth,token=token+"tampered")


def test_v417_dedicated_connection_failure_and_identity_denied():
    def unreachable(*args,**kwargs):
        raise ConnectionError("example-password")
    report,_=invoke(connect=unreachable)
    assert report["status"]=="V417_RESTRICTED_READER_UNAVAILABLE_HELD"
    assert "example-password" not in str(report)
    report,_=invoke(identity=("postgres","empire_predictive_cash_candidate_reader"))
    assert report["status"]=="V417_RESTRICTED_LOGIN_IDENTITY_INVALID_HELD"


def test_v417_requires_original_owner_supplied_dsn():
    with pytest.raises(ValueError,match="OWNER_MANAGED_DSN"):
        invoke(dsn="")


def test_v417_readers_wont_promote_prospects_or_cash():
    report,_=invoke()
    for name in (
        "gtm_opportunity_denominator_complete",
        "historical_status_as_of_window_end_verified",
        "settled_cash_independently_verified",
        "refunds_reconciled_to_finance",
        "customer_conversion_rate_verified",
        "eligible_for_revenue_forecast_calibration",
        "economic_memory_write_authorized",
        "buyer_outreach_authorized",
        "paid_traffic_authorized",
        "funds_movement_authorized",
    ):
        assert report[name] is False


def test_v417_migration_depends_on_original_reader_with_no_new_roles():
    text=MIGRATION.read_text()
    assert "PREPARED ONLY" in text
    assert "public.empire_current_tenant_id()" in text
    assert "V417_ORIGINAL_067_REQUIRED" in text
    assert "V417_ORIGINAL_068_REQUIRED" in text
    assert "p_end-p_start>interval '31 days'" in text
    assert "v_total>5000" in text
    assert "JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant" in text
    assert "o.created_at>=p_start AND o.created_at<p_end" in text
    assert "complete_gtm_opportunity_denominator_verified:=false" in text
    assert "historical_status_as_of_window_end_verified:=false" in text
    assert "settled_cash_independently_verified:=false" in text
    for forbidden in ("CREATE ROLE ","CREATE DATABASE ","CREATE TABLE "):
        assert forbidden not in text


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="isolated PG18 missing")
def test_v417_original_empiredb_disposable_pg18_cohort_067_068_069():
    proc=subprocess.run(["pg_virtualenv","-t","bash",str(SCRIPT)],
        cwd=ROOT,text=True,capture_output=True,timeout=120,
    )
    assert proc.returncode==0,(proc.stdout+proc.stderr)[-2400:]
    receipts=[json.loads(line) for line in proc.stdout.splitlines()
              if line.startswith("{")]
    assert len(receipts)==1
    receipt=receipts[0]
    assert receipt["status"]=="V417_EPHEMERAL_ORDER_COHORT_PASS"
    assert receipt["pg18_isolated"] is True
    assert receipt["production_db_writes"] is False
    assert receipt["live_payments_enabled"] is False
    assert "Dropping cluster 18/regress" in proc.stdout+proc.stderr


def test_v417_fixture_refuses_production_port():
    proc=subprocess.run(["bash",str(SCRIPT)],
        cwd=ROOT,env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
        text=True,capture_output=True,timeout=8,
    )
    assert proc.returncode!=0
    assert "V417_EPHEMERAL_ORDER_COHORT_PASS" not in proc.stdout


def test_v417_no_payment_or_model_side_effects():
    text=(ROOT/"empire_os/predictive_revenue_v417_order_cohort.py").read_text()
    for name in ("CREATE TABLE ","create_engine(", "commit(",
                 "execute_payment(", "execute_trade(", "send_email(",
                 "systemctl", "redis.Redis(", "model.fit("):
        assert name not in text
