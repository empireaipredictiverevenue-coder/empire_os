"""V4.21 signed, tenant-bound six-stage HELD lifecycle + offline calibration."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json,os,runpy,shutil,subprocess
from pathlib import Path

import pytest
from empire_os.predictive_revenue_v421_lifecycle import (
    SCHEMA as LIFECYCLE_SCHEMA,review_v421_six_stage_held,
)
from empire_os.predictive_revenue_v421_calibration import (
    SCHEMA as CALIBRATION_SCHEMA,score_v421_offline_residuals_held,
)

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/073_predictive_revenue_v421_lifecycle_held.sql"
SCRIPT=ROOT/"scripts/rehearse_predictive_revenue_v421_lifecycle_20261025.sh"
v420=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v420_three_pillar_20261025.py"))
v418=runpy.run_path(str(ROOT/"tests/test_predictive_revenue_v418_opportunities_20261025.py"))
SIGNED=v418["SIGNED"]
TWIN=v418["TWIN"]
TENANT=v418["TENANT"]
OTHER=v418["OTHER"]
NOW=datetime.now(timezone.utc)
PRIOR=(6,6,6,3,3,3,1,1,Decimal(600),5000,
       False,False,False,False,False,False)
LIFECYCLE=(6,6,3,3,1,1,1,1,
           Decimal(25000),Decimal(1300),Decimal(600),Decimal(23100),
           False,False,False,False,False,False)


class Cursor:
    def __init__(self,past,new,identity=(
        "empire_predictive_cash_candidate_login",
        "empire_predictive_cash_candidate_reader",
    )):
        self.past=past;self.new=new;self.identity=identity
        self.queries=[];self.stage=0
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,sql,args=None):
        self.queries.append((sql,args))
        if sql.startswith("SELECT opportunity_count"):self.stage=1
        if sql.startswith("SELECT opportunity_count,claimed_authorized"):self.stage=2
    def fetchone(self):return self.identity
    def fetchall(self):
        if self.stage==1:return self.past
        return self.new


class Conn:
    def __init__(self,c):self.c=c
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return self.c


def invoke_lifecycle(*,prior=None,latest=None,identity=None,token=None,
                     verifier=None,model=None,connect=None):
    if verifier is None:
        verifier,bearer=SIGNED()
        if token is None:token=bearer
    cur=Cursor([PRIOR] if prior is None else prior,
               [LIFECYCLE] if latest is None else latest,
               identity=identity or (
                   "empire_predictive_cash_candidate_login",
                   "empire_predictive_cash_candidate_reader",
               ))
    if connect is None:connect=lambda dsn,**kwargs:Conn(cur)
    out=review_v421_six_stage_held(
        research_twin=TWIN() if model is None else model,
        signed_crm_bearer=token,crm_verifier=verifier,channel_name="organic",
        window_start=NOW-timedelta(days=14),window_end=NOW-timedelta(days=1),
        dedicated_cash_dsn="test-only",connect_factory=connect,
    )
    return out,cur


def test_v421_injected_lifecycle_cannot_report_real_cash():
    out,cur=invoke_lifecycle()
    assert out["schema_version"]==LIFECYCLE_SCHEMA
    assert out["status"]=="V421_INJECTED_CONNECTOR_NOT_PROOF_HELD"
    assert out["stage_2_claimed_opportunity_denominator"] is None
    assert out["realised_net_cash_verified_minor"] is None
    assert out["model_weights_updated"] is False
    assert out["calibrated_30_60_90_forecasts"] is None
    assert out["execution_authority"]=="none"
    assert cur.queries[0][0]=="SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert cur.queries[2][0]=="SET LOCAL ROLE empire_predictive_cash_candidate_reader"
    assert cur.queries[4][1]==cur.queries[5][1]


@pytest.mark.parametrize("row",[
    (7,6,3,3,1,1,1,1,25000,1300,600,23100,False,False,False,False,False,False),
    (6,6,3,3,2,1,1,1,25000,1300,600,23100,False,False,False,False,False,False),
    (6,6,3,3,1,1,2,1,25000,1300,600,23100,False,False,False,False,False,False),
    (6,6,3,3,1,1,1,1,25000,1300,600,23000,False,False,False,False,False,False),
    (6,6,3,3,1,1,1,1,25000,-1300,600,25700,False,False,False,False,False,False),
    (6,6,3,3,1,1,1,1,25000,1300,600,23100,False,True,False,False,False,False),
    (6,6,3,3,1,1,1,1,25000,1300,600,23100,False,False,True,False,False,False),
    (6,6,3,3,1,1,1,1,25000,1300,600,23100,False,False,False,True,False,False),
    (6,6,3,3,1,1,1,1,25000,1300,600,23100,False,False,False,False,True,False),
    (6,6,3,3,1,1,1,1,25000,1300,600,23100,False,False,False,False,False,True),
    (6,6,3,3,1,1,1,1,25000,1300,600,23100,False,False,False,False,False),
])
def test_v421_forged_cash_or_incomplete_lifecycle_fails_closed(row):
    out,_=invoke_lifecycle(latest=[row])
    assert out["status"]!="V421_SIX_STAGE_CLAIMED_LIFECYCLE_ONLY_HELD"
    assert out["stage_2_claimed_opportunity_denominator"] is None
    assert out["cash_baseline_verified_for_training"] is False


def test_v421_missing_rows_and_wrong_principal_are_unknown():
    out,_=invoke_lifecycle(latest=[])
    assert out["status"]=="V421_INCOMPLETE_LIFECYCLE_JOIN_HELD"
    assert out["stage_2_claimed_opportunity_denominator"] is None
    out,_=invoke_lifecycle(identity=("postgres","empire_predictive_cash_candidate_reader"))
    assert out["status"]=="V421_ORIGINAL_READER_IDENTITY_INVALID_HELD"
    model=TWIN();model["canonical_tenant_id"]=OTHER
    with pytest.raises(ValueError,match="TENANT_MISMATCH"):
        invoke_lifecycle(model=model)
    verifier,token=SIGNED()
    with pytest.raises(ValueError,match="ACTIVE_SIGNED_CRM"):
        invoke_lifecycle(verifier=verifier,token=token+"tamper")


# Founder-provided 100,000-opportunity matrix is hypothetical, not bank evidence.
ILLUSTRATIVE=(
    ("ppl",64033590,1280000,22776840,41256750),
    ("storm",132866800,4500000,9922789,122944011),
    ("saas",22289800,450000,4990782,17299018),
    ("ecommerce",7359105,820000,12628678,-5269573),
)


def scenario_rows():
    rows=[]
    for index,(sector,gross,refund,cost,forecast) in enumerate(ILLUSTRATIVE):
        start=NOW-timedelta(days=160-index)
        rows.append({
            "cohort_id":f"scenario:{sector}",
            "tenant_id":TENANT,"currency_code":"USD",
            "source_evidence_digest":"a"*64,
            "niche":sector,"horizon_days":90,
            "forecast_locked_at":(start-timedelta(days=1)).isoformat(),
            "cohort_start_utc":start.isoformat(),
            "gross_claim_minor":gross,
            "refund_claim_minor":refund,
            "acquisition_cost_minor":cost,
            "forecast_net_minor":forecast,
            "outcome_observed_at":(NOW-timedelta(hours=1)).isoformat(),
            "source_rights_verified":False,
            "bank_settlement_verified":False,
            "refund_finality_verified":False,
        })
    return tuple(rows)


def calibration(rows=None,**kwargs):
    verifier,token=SIGNED()
    return score_v421_offline_residuals_held(
        research_twin=TWIN(),signed_crm_bearer=token,
        crm_verifier=verifier,claimed_scenarios=scenario_rows() if rows is None else rows,
        as_of=NOW,**kwargs,
    )


def test_v421_user_matrix_arithmetic_is_sensitivity_not_model_fit():
    result=calibration()
    assert result["schema_version"]==CALIBRATION_SCHEMA
    assert result["claimed_scenario_count"]==4
    horizon=result["horizons"][2]
    assert horizon["claimed_aggregate_actual_net_minor"]==169180206
    assert horizon["forecast_net_total_minor"]==176230206
    assert horizon["claimed_residual_minor"]==-7050000
    assert horizon["illustrative_older_train_ratio_not_production_lambda"] is None
    assert horizon["production_lambda"] is None
    assert result["model_weights_updated"] is False
    assert result["training_samples_written"] is False
    assert result["live_30_60_90_forecast_activation"] is False


def test_v421_signed_losses_do_not_turn_into_positive_lambda():
    rows=scenario_rows()
    assert rows[-1]["forecast_net_minor"] < 0
    assert rows[-1]["gross_claim_minor"]-rows[-1]["refund_claim_minor"]-rows[-1]["acquisition_cost_minor"] < 0
    result=calibration()
    assert result["signed_cash_and_negative_margin_supported"] is True
    assert result["horizons"][2]["older_train_count"]==0
    assert result["verified_cash_model_calibration"] is False


@pytest.mark.parametrize("mutate",[
    lambda r:r.update(bank_settlement_verified=True),
    lambda r:r.update(refund_finality_verified=True),
    lambda r:r.update(source_rights_verified=True),
    lambda r:r.update(forecast_net_minor=1.5),
    lambda r:r.update(tenant_id=OTHER),
    lambda r:r.update(currency_code="GBP"),
    lambda r:r.update(cohort_start_utc=r["forecast_locked_at"]),
])
def test_v421_forged_attestations_and_causal_leakage_rejected(mutate):
    rows=[dict(x) for x in scenario_rows()]
    mutate(rows[0])
    with pytest.raises(ValueError):
        calibration(tuple(rows))


def test_v421_missing_cash_keeps_horizon_unknown():
    rows=[dict(x) for x in scenario_rows()]
    rows[0]["gross_claim_minor"]=None
    rows[0]["outcome_observed_at"]=None
    outcome=calibration(tuple(rows))
    assert outcome["horizons"][2]["claimed_aggregate_actual_net_minor"] is None
    assert outcome["missing_claimed_outcomes"]>=1
    assert outcome["verified_cash_model_calibration"] is False


def test_v421_chronological_holdout_lambda_is_research_only():
    rows=[]
    for index in range(15):
        row=dict(scenario_rows()[0])
        start=NOW-timedelta(days=170-index)
        row["cohort_id"]=f"scenario:historical:{index:02d}"
        row["forecast_locked_at"]=(start-timedelta(days=1)).isoformat()
        row["cohort_start_utc"]=start.isoformat()
        row["forecast_net_minor"]=1000
        row["gross_claim_minor"]=1100+index*10
        row["refund_claim_minor"]=0
        row["acquisition_cost_minor"]=0
        rows.append(row)
    report=calibration(tuple(rows))
    ninety=report["horizons"][2]
    assert ninety["older_train_count"]==10
    assert ninety["heldout_test_count"]==5
    assert ninety["illustrative_older_train_ratio_not_production_lambda"] is not None
    assert ninety["holdout_raw_mae_minor"] is not None
    assert ninety["production_lambda"] is None
    assert report["model_weights_updated"] is False
    assert report["training_samples_written"] is False


def test_v421_duplicate_scenario_ids_refused():
    rows=list(scenario_rows())
    rows[1]=dict(rows[1],cohort_id=rows[0]["cohort_id"])
    with pytest.raises(ValueError,match="UNIQUE_COHORT"):
        calibration(tuple(rows))


def test_v421_schema_stays_additive_and_held():
    text=MIGRATION.read_text()
    assert "PREPARED ONLY" in text
    assert "V421_SESSION_TENANT_DENIED" in text
    assert "public.empire_predictive_refund_clawback_claims_v421" in text
    assert "V421_BOUNDED_COHORT_REQUIRED" in text
    assert "false,false,false,false,false,false" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "GRANT EXECUTE ON FUNCTION" in text
    assert "CREATE DATABASE " not in text
    assert "CREATE ROLE " not in text


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,reason="disposable PostgreSQL18 unavailable")
def test_v421_real_disposable_postgres_067_to_073_original_boundaries():
    p=subprocess.run(["pg_virtualenv","-t","bash",str(SCRIPT)],
        cwd=ROOT,text=True,capture_output=True,timeout=130)
    assert p.returncode==0,(p.stdout+p.stderr)[-2500:]
    receipt=[json.loads(x) for x in p.stdout.splitlines() if x.startswith("{")]
    assert len(receipt)==1
    assert receipt[0]["status"]=="V421_EPHEMERAL_SIX_STAGE_PASS"
    assert receipt[0]["production_db_writes"] is False
    assert receipt[0]["live_payments_enabled"] is False
    assert "Dropping cluster 18/regress" in p.stdout+p.stderr


def test_v421_pg18_rehearsal_refuses_live_database_port():
    p=subprocess.run(["bash",str(SCRIPT)],
        cwd=ROOT,env={**os.environ,"PGHOST":"localhost","PGPORT":"5432"},
        text=True,capture_output=True,timeout=8)
    assert p.returncode!=0
    assert "V421_EPHEMERAL_SIX_STAGE_PASS" not in p.stdout
