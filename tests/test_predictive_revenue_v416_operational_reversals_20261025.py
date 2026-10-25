"""V4.16 operational reversal signals are never financial refund or net cash."""
from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

from empire_os.predictive_revenue_v416_operational_reversals import (
    SCHEMA, STATES, review_v416_reversal_signals_held,
)

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/068_predictive_revenue_operational_reversal_signals_held.sql"
SHELL=ROOT/"scripts/rehearse_predictive_revenue_v416_reversals_20261025.sh"
OLD=runpy.run_path(str(
    ROOT/"tests/test_predictive_revenue_v415_direct_cash_reader_20261025.py"
))
SIGNED=OLD["signed"]
TWIN=OLD["twin"]
ORDER=OLD["ORDER"]
ORDER2=OLD["ORDER2"]
TENANT=OLD["TENANT"]
OTHER=OLD["OTHER"]


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
    def __init__(self,cursor):self._cursor=cursor
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return self._cursor


def invoke(*,rows=None,identity=None,order_ids=(ORDER,),
           twin=None,token=None,verifier=None,connect=None,dsn="ephemeral-fixture"):
    if rows is None:
        rows=[(ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,False,False,False,False)]
    cur=Cursor(rows,identity=identity) if identity is not None else Cursor(rows)
    if verifier is None:
        verifier,real_token=SIGNED()
        if token is None:token=real_token
    if connect is None:
        connect=lambda dsn,**kwargs:Connection(cur)
    return review_v416_reversal_signals_held(
        research_twin=TWIN() if twin is None else twin,
        signed_crm_bearer=token,crm_verifier=verifier,
        exact_order_ids=order_ids,
        dedicated_cash_dsn=dsn,connect_factory=connect,
    ),cur


def test_v416_operational_refund_is_not_money_and_mock_is_held():
    result,cur=invoke()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="V416_TEST_CONNECTOR_NOT_INDEPENDENT_EVIDENCE_HELD"
    assert result["orders_with_refund_like_delivery_signal"]==0
    assert result["net_cash_earned_minor_units"] is None
    assert result["full_opportunity_cohort_verified"] is False
    assert result["refund_and_chargeback_finality_verified"] is False
    assert result["absence_of_refund_signal_proves_refund_absence"] is False
    assert result["original_postgresql_connector_used"] is False
    assert result["execution_authority"]=="none"
    assert cur.statements[0][0]=="SET TRANSACTION READ ONLY"
    assert cur.statements[2][0]=="SET LOCAL ROLE empire_predictive_cash_candidate_reader"
    assert cur.statements[4][1]==(TENANT,[ORDER])


@pytest.mark.parametrize("state,a,b", [
    ("REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0),
    ("FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD",0,1),
    ("NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD",0,0),
    ("ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD",0,0),
])
def test_v416_all_supported_operational_signals_are_held(state,a,b):
    report,_=invoke(rows=[(ORDER,state,a,b,False,False,False,False)])
    assert report["status"]=="V416_TEST_CONNECTOR_NOT_INDEPENDENT_EVIDENCE_HELD"
    assert report["net_cash_earned_minor_units"] is None
    assert state in STATES


@pytest.mark.parametrize("row", [
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",0,0,False,False,False,False),
    (ORDER,"NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD",1,0,False,False,False,False),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,True,False,False,False),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,False,True,False,False),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,False,False,True,False),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,False,False,False,True),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",-1,0,False,False,False,False),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",True,0,False,False,False,False),
    (ORDER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,False,False,False),
    (OTHER,"REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0,False,False,False,False),
    (ORDER,"FINANCIAL_REFUND_CONFIRMED",1,0,False,False,False,False),
])
def test_v416_forged_or_overprivileged_rows_fail_closed(row):
    report,_=invoke(rows=[row])
    assert report["status"]!="V416_BOUNDED_OPERATIONAL_REVERSAL_OBSERVATIONS_HELD"
    assert report["orders_with_refund_like_delivery_signal"]==0
    assert report["funds_movement_authorized"] is False


def test_v416_wrong_db_identity_and_missing_schema_are_not_positive():
    report,_=invoke(identity=("postgres","empire_predictive_cash_candidate_reader"))
    assert report["status"]=="V416_READER_IDENTITY_INVALID_HELD"
    def unavailable(*args,**kwargs):
        raise ConnectionError("confidential database credential")
    report,_=invoke(connect=unavailable)
    assert report["status"]=="V416_READER_NOT_AVAILABLE_HELD"
    assert "confidential" not in str(report)


def test_v416_forged_twin_and_tenant_crossing_rejected():
    model=TWIN();model["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_MISMATCH"):
        invoke(twin=model)
    model=TWIN();model["licensed_source_admitted"]=True
    with pytest.raises(ValueError,match="ORIGINAL_SIMULATION"):
        invoke(twin=model)


@pytest.mark.parametrize("ids",[(),(ORDER,ORDER),(ORDER,"bad"),(ORDER,)*9,[ORDER]])
def test_v416_bounded_distinct_explicit_orders_required(ids):
    with pytest.raises(ValueError,match="UNIQUE_BOUNDED"):
        invoke(order_ids=ids)


def test_v416_bad_signatures_or_clueless_reader_refused():
    with pytest.raises(ValueError,match="OWNER_MANAGED_READER_DSN_REQUIRED"):
        invoke(dsn="")
    ver,token=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_SIGNED_CRM"):
        invoke(verifier=ver,token=token+"modified")


def test_v416_prepared_sql_preserves_original_067_roles_and_false_finality():
    sql=MIGRATION.read_text()
    assert "PREPARED ONLY" in sql
    assert "V416_MIGRATION_067_NOT_PRESENT" in sql
    assert "public.empire_current_tenant_id()" in sql
    assert "commercial_outcomes" in sql
    assert "delivery_outcome='refunded'" in sql
    assert "b.org_id=v_tenant" in sql
    for name in ("monetary_reversal_independently_verified",
                 "full_refund_census_verified","net_cash_earned_verified",
                 "automatic_execution_authorized"):
        assert name+":=false" in sql
    assert "CREATE ROLE " not in sql
    assert "CREATE TABLE " not in sql
    assert "CREATE DATABASE " not in sql


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="isolated PG18 missing")
def test_v416_original_db_067_and_068_disposable_pg18_rehearsal():
    proc=subprocess.run(["pg_virtualenv","-t","bash",str(SHELL)],
       cwd=ROOT,text=True,capture_output=True,timeout=100,
    )
    assert proc.returncode==0,(proc.stdout+proc.stderr)[-2000:]
    receipts=[json.loads(s) for s in proc.stdout.splitlines() if s.startswith("{")]
    assert len(receipts)==1
    r=receipts[0]
    assert r["status"]=="V416_EPHEMERAL_REVERSAL_SIGNAL_PASS"
    assert r["pg18_isolated"] is True
    assert r["production_db_writes"] is False
    assert r["live_payments_enabled"] is False
    assert "Dropping cluster 18/regress" in proc.stdout+proc.stderr


def test_v416_fixture_refuses_host_without_disposable_pg_virtualenv():
    proc=subprocess.run(["bash",str(SHELL)],cwd=ROOT,
        env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
        capture_output=True,text=True,timeout=8,
    )
    assert proc.returncode!=0
    assert "V416_EPHEMERAL_REVERSAL_SIGNAL_PASS" not in proc.stdout


def test_v416_no_payment_side_effect_or_new_database():
    s=(ROOT/"empire_os/predictive_revenue_v416_operational_reversals.py").read_text()
    for bad in ("execute_payment(", "send_email(", "CREATE TABLE",
                "create_engine(", "commit(", "systemctl",
                "redis.Redis(", "execute_trade(", "approve_transfer("):
        assert bad not in s
