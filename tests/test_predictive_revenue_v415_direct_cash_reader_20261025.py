"""V4.15 original CRM-bound HELD direct BSC cash evidence reader tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
import base64
import json
import os
import shutil
import subprocess

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_revenue_v415_direct_cash_reader import (
    review_v415_cash_candidates_held, SCHEMA, READER_LOGIN,
    CAPABILITY_ROLE, POSITIVE, NEGATIVE,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/067_predictive_direct_bsc_cash_candidate_held.sql"
SCRIPT=ROOT/"scripts/rehearse_predictive_revenue_v415_cash_reader_20261025.sh"
TENANT="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ORDER="33333333-3333-4333-8333-333333333333"
ORDER2="55555555-5555-4555-8555-555555555555"
NOW=1800000000


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def signed():
    private=Ed25519PrivateKey.generate()
    v=SignedCrmTenantVerifier(
        {"fixture":private.public_key()},
        load_membership=lambda sub,tenant:TenantMembership(
            tenant_id=TENANT,user_id=sub,role="owner",status="active",
        ),
        now=lambda:NOW,
    )
    header=b64(json.dumps({"alg":"EdDSA","kid":"fixture","typ":"JWT"}).encode())
    payload=b64(json.dumps({
        "iss":"empire-os","aud":"empire-revenue-crm","sub":"founder-1",
        "tenant_id":TENANT,"scope":"crm:read",
        "iat":NOW-10,"nbf":NOW-10,"exp":NOW+120,
        "jti":"v415-owner-readonly-01",
    }).encode())
    unsigned=header+"."+payload
    return v,unsigned+"."+b64(private.sign(unsigned.encode()))


def twin():
    return {
        "schema_version":"empire.predictive_revenue.v412.synthetic_cash_twin.v1",
        "mode":"SIMULATION","simulation_only":True,
        "execution_authority":"none",
        "licensed_source_admitted":False,
        "forecast_empirically_calibrated":False,
        "approved_commercial_forecast":False,
        "revenue_recognised_cents":None,
        "currency_code":"USD",
        "canonical_tenant_id":TENANT,
        "source_evidence_digest":"a"*64,
        "forecast_horizons":{
            k:{
                "p10_gross_cash_cents":0,
                "p50_gross_cash_cents":0,
                "p90_gross_cash_cents":0,
            } for k in ("30","60","90")
        },
    }


class Cursor:
    def __init__(self,rows,identity=(READER_LOGIN,CAPABILITY_ROLE)):
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


def invoke(*,rows=None,identity=(READER_LOGIN,CAPABILITY_ROLE),ids=(ORDER,),data=None,
           verifier=None,token=None,dsn="mock-dedicated-credentials",factory=None):
    if rows is None:rows=[(ORDER,POSITIVE,25000,True,False,False,False)]
    cur=Cursor(rows,identity)
    if verifier is None:
        verifier,signed_token=signed()
        if token is None:token=signed_token
    if factory is None:factory=lambda dsn,**k:Connection(cur)
    result=review_v415_cash_candidates_held(
        research_twin=twin() if data is None else data,
        signed_crm_bearer=token,
        crm_verifier=verifier,
        exact_order_ids=ids,
        dedicated_cash_dsn=dsn,
        connect_factory=factory,
    )
    return result,cur


def test_v415_mock_candidate_never_becomes_independently_verified_cash():
    result,cursor=invoke()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="V415_TEST_INJECTED_CONNECTOR_NOT_SOURCE_PROOF_HELD"
    assert result["original_postgresql_connector_used"] is False
    assert result["database_endpoint_independently_attested"] is False
    assert result["direct_transfer_candidate_count"]==0
    assert result["unknown_or_unverified_order_count"]==1
    assert result["claim_not_collected_cash"] is True
    assert result["actual_cash_collected_minor_units"] is None
    assert result["revenue_forecast_calibration_eligible"] is False
    for name in ("commercial_delivery_authorized","paid_traffic_authorized",
                 "funds_movement_authorized","actual_revenue_recognized_by_this_read"):
        assert result[name] is False
    assert cursor.statements[0][0]=="SET TRANSACTION READ ONLY"
    assert cursor.statements[2][0]=="SET LOCAL ROLE "+CAPABILITY_ROLE
    assert cursor.statements[4][1] == (TENANT,[ORDER])


def test_v415_explicit_unknown_order_not_false_zero():
    report,_=invoke(rows=[(ORDER,NEGATIVE,None,False,False,False,False)])
    assert report["direct_transfer_candidate_count"]==0
    assert report["unknown_or_unverified_order_count"]==1
    assert report["actual_cash_collected_minor_units"] is None


@pytest.mark.parametrize("row",[
    (ORDER,POSITIVE,25000,True,False,True,False),
    (ORDER,POSITIVE,25000,True,True,False,False),
    (ORDER,POSITIVE,25000,True,False,False,True),
    (ORDER,POSITIVE,0,True,False,False,False),
    (ORDER,POSITIVE,None,True,False,False,False),
    (ORDER,POSITIVE,25000,False,False,False,False),
    (ORDER,NEGATIVE,25000,False,False,False,False),
    (ORDER,NEGATIVE,None,True,False,False,False),
    (ORDER,"APPROVED_FOR_CASH",25000,True,False,False,False),
    (ORDER,POSITIVE,25000,1,False,False,False),
    (OTHER,POSITIVE,25000,True,False,False,False),
    (ORDER,POSITIVE,25000,True,False,False),
])
def test_v415_rejects_forged_production_reply(row):
    report,_=invoke(rows=[row])
    assert report["status"] != "V415_SCOPED_DIRECT_TRANSFER_CANDIDATES_ONLY_HELD"
    assert report["direct_transfer_candidate_count"]==0
    assert report["funds_movement_authorized"] is False


def test_v415_rejects_duplicate_or_partial_result_sets():
    report,_=invoke(rows=[
        (ORDER,POSITIVE,25000,True,False,False,False),
        (ORDER,POSITIVE,25000,True,False,False,False),
    ],ids=(ORDER,ORDER2))
    assert report["direct_transfer_candidate_count"]==0
    report,_=invoke(rows=[],ids=(ORDER,))
    assert report["status"]=="V415_INCOMPLETE_OR_DUPLICATE_RESULT_HELD"


@pytest.mark.parametrize("ids",[
    (), (ORDER,ORDER), (ORDER,"bad"), (ORDER,)*9,
    (ORDER,"00000000-0000-0000-0000-000000000000"),
    [ORDER],
])
def test_v415_bounded_unique_canonical_order_list(ids):
    with pytest.raises(ValueError,match="BOUNDED_UNIQUE"):
        invoke(ids=ids)


def test_v415_rejects_tenant_mismatch_or_forged_twin():
    forged=twin();forged["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="CRM_TWIN_TENANT"):
        invoke(data=forged)
    forged=twin();forged["approved_commercial_forecast"]=True
    with pytest.raises(ValueError,match="NONPROMOTABLE_TWIN"):
        invoke(data=forged)


def test_v415_reader_login_session_must_be_exact():
    data,_=invoke(identity=("postgres",CAPABILITY_ROLE))
    assert data["status"]=="V415_DEDICATED_READER_IDENTITY_INVALID_HELD"


def test_v415_dsn_unavailable_not_declare_verified_cash():
    def blocked(*args,**kwargs):
        raise ConnectionError("password fake secret must not appear")
    result,_=invoke(factory=blocked)
    assert result["status"]=="V415_DEDICATED_READER_UNAVAILABLE_HELD"
    assert "fake secret" not in str(result)


def test_v415_reject_bad_owner_dsn_or_crm_token():
    with pytest.raises(ValueError,match="DEDICATED_CASH"):
        invoke(dsn="")
    v,tok=signed()
    with pytest.raises(ValueError,match="ACTIVE_CRM"):
        invoke(verifier=v,token=tok+"tamper")


def test_v415_held_migration_requires_owner_and_never_provisions_login():
    sql=MIGRATION.read_text()
    assert "PREPARED ONLY" in sql
    assert "V415_WRONG_DATABASE" in sql
    assert "V415_DEDICATED_NOLOGIN_READER_ROLE_REQUIRED" in sql
    assert "V415_READER_CAPABILITY_ALREADY_ASSIGNED_REVIEW" in sql
    assert "V415_SESSION_BOUND_TENANT_REQUIRED" in sql
    assert "public.empire_current_tenant_id()" in sql
    assert "p_order_ids uuid[]" in sql and "BETWEEN 1 AND 8" in sql
    assert "d.chain_id=56" in sql and "d.confirmations>=12" in sql
    assert "r.settlement_mode='direct'" in sql
    assert "independent_refund_finality_verified := false" in sql
    assert "cash_collected_by_finance_verified := false" in sql
    assert "commercial_action_authorized := false" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "CREATE ROLE " not in sql and "CREATE DATABASE " not in sql


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="disposable PG18 unavailable")
def test_v415_actual_disposable_postgres18_rights_and_onchain_transfer_holds():
    process=subprocess.run(
        ["pg_virtualenv","-t","bash",str(SCRIPT)],
        cwd=ROOT,text=True,capture_output=True,timeout=85,
    )
    assert process.returncode==0,process.stdout[-3000:]+process.stderr[-3000:]
    receipt=[json.loads(v) for v in process.stdout.splitlines() if v.startswith("{")]
    assert len(receipt)==1
    report=receipt[0]
    assert report["status"]=="V415_EPHEMERAL_DIRECT_USDT_READ_PASS"
    for k in (
        "pg18_isolated","dedicated_login_and_set_only_reader",
        "one_valid_direct_transfer_candidate","cross_tenant_unknown",
        "escrow_not_inferred","low_confirmation_not_inferred",
        "duplicate_selection_denied","direct_table_select_denied",
    ):
        assert report[k] is True
    for k in (
        "candidate_is_final_cash","cash_refund_finality_verified",
        "production_db_writes","live_payments_enabled",
    ):
        assert report[k] is False
    assert "Dropping cluster 18/regress" in process.stdout+process.stderr


def test_v415_fixture_cannot_run_on_production_default_port():
    process=subprocess.run(["bash",str(SCRIPT)],
        cwd=ROOT,env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
        capture_output=True,text=True,timeout=6,
    )
    assert process.returncode != 0
    assert "V415_EPHEMERAL_DIRECT_USDT_READ_PASS" not in process.stdout


def test_v415_python_reader_never_creates_db_or_executes_payments():
    py=(ROOT/"empire_os/predictive_revenue_v415_direct_cash_reader.py").read_text()
    for forbidden in (
        "create_engine(", "create_all(", "CREATE TABLE",
        "commit(", "systemctl", "send_message(",
        "send_email(", "execute_payment(", "execute_trade(",
        "redis.Redis(", "router.post(",
    ):
        assert forbidden not in py
