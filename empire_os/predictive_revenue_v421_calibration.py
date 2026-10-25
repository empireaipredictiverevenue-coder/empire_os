"""Offline V4.21 claimed-cash residuals. NO independently verified cash or training.

Use immutable integer minor-unit scenarios, strict tenant/time lineage and
signed results. A negative forecast or cohort is never safe for a naive
multiplicative lambda. This module never updates production model weights.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from hashlib import sha256
from typing import Any
import json
from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA="empire.predictive_revenue.v421.offline_claimed_cash_calibration_held.v1"
FIELDS=frozenset({
 "cohort_id","tenant_id","currency_code","source_evidence_digest",
 "niche","horizon_days","forecast_locked_at","cohort_start_utc",
 "gross_claim_minor","refund_claim_minor","acquisition_cost_minor",
 "forecast_net_minor","outcome_observed_at","source_rights_verified",
 "bank_settlement_verified","refund_finality_verified",
})
LIMIT=10**13

def _time(s:object)->datetime:
    if type(s) is not str or len(s)>40:raise ValueError("V421_TIMESTAMP_REQUIRED")
    try:
        parsed=datetime.fromisoformat(s.replace("Z","+00:00"))
        if parsed.utcoffset() is None:raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError,TypeError):
        raise ValueError("V421_AWARE_TIMESTAMP_REQUIRED") from None

def score_v421_offline_residuals_held(
 *,research_twin:dict[str,Any],signed_crm_bearer:str,
 crm_verifier:SignedCrmTenantVerifier,
 claimed_scenarios:tuple[dict[str,Any],...],as_of:datetime,
)->dict[str,Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V421_ORIGINAL_SIMULATION_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V421_ORIGINAL_SIGNED_CRM_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V421_BEARER_REQUIRED")
    if type(as_of) is not datetime or as_of.utcoffset() is None:
        raise ValueError("V421_AWARE_CUTOFF_REQUIRED")
    if type(claimed_scenarios) is not tuple or not 1<=len(claimed_scenarios)<=240:
        raise ValueError("V421_BOUNDED_SCENARIOS_REQUIRED")
    try:tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:raise ValueError("V421_ACTIVE_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V421_TENANT_MISMATCH")
    now=as_of.astimezone(timezone.utc)
    seen:set[str]=set()
    records=[]
    missing=0
    immature=0
    for row in claimed_scenarios:
        if type(row) is not dict or set(row)!=FIELDS:
            raise ValueError("V421_EXACT_SCENARIO_FIELDS_REQUIRED")
        key=row["cohort_id"]
        if (type(key) is not str or not 4<=len(key)<=100 or not key.isascii()
            or any(x.isspace() for x in key) or key in seen):
            raise ValueError("V421_UNIQUE_COHORT_ID_REQUIRED")
        seen.add(key)
        if (row["tenant_id"]!=tenant
            or row["currency_code"]!=research_twin["currency_code"]
            or row["source_evidence_digest"]!=research_twin["source_evidence_digest"]):
            raise ValueError("V421_TENANT_SOURCE_CURRENCY_MISMATCH")
        if (type(row["niche"]) is not str or not 1<=len(row["niche"])<=60
            or type(row["horizon_days"]) is not int
            or row["horizon_days"] not in (30,60,90)):
            raise ValueError("V421_EXACT_HORIZON_SECTOR_REQUIRED")
        if any(row[flag] is not False for flag in (
            "source_rights_verified","bank_settlement_verified",
            "refund_finality_verified",
        )):
            raise ValueError("V421_UNAUTHENTICATED_FINANCIAL_ATTESTATION")
        frozen=_time(row["forecast_locked_at"])
        start=_time(row["cohort_start_utc"])
        observed=_time(row["outcome_observed_at"]) if row["outcome_observed_at"] is not None else None
        if frozen>=start or start>now:
            raise ValueError("V421_FORECAST_CAUSAL_ORDER_VIOLATED")
        target=start+timedelta(days=row["horizon_days"])
        if target>now:immature+=1
        if observed is not None and (observed<=target or observed>now):
            raise ValueError("V421_OUTCOME_FINALITY_TIMESTAMP_INVALID")
        if observed is None:missing+=1
        for k in ("gross_claim_minor","refund_claim_minor","acquisition_cost_minor"):
            v=row[k]
            if v is not None and (type(v) is not int or not 0<=v<=LIMIT):
                raise ValueError("V421_NONNEGATIVE_INTEGER_CLAIM_REQUIRED")
        estimate=row["forecast_net_minor"]
        if type(estimate) is not int or not -LIMIT<=estimate<=LIMIT:
            raise ValueError("V421_SIGNED_FORECAST_INTEGER_REQUIRED")
        gross,refund,cost=(row[k] for k in
            ("gross_claim_minor","refund_claim_minor","acquisition_cost_minor"))
        if observed is None or None in (gross,refund,cost):
            missing+=int(observed is not None)
            actual=None
        else:
            actual=gross-refund-cost
        records.append((key,row["horizon_days"],start,frozen,estimate,actual))

    groups=[]
    for horizon in (30,60,90):
        part=sorted((x for x in records if x[1]==horizon),key=lambda r:r[2])
        fully_mature=bool(part) and all(
            start+timedelta(days=horizon)<=now and cash is not None
            for _,_,start,_,_,cash in part
        )
        scenarios=[(forecast,cash) for _,_,_,_,forecast,cash in part if cash is not None]
        claimed_total=sum(y for _,y in scenarios)
        predicted_total=sum(p for p,_ in scenarios)
        residual=claimed_total-predicted_total if fully_mature else None
        # The only proposed lambda comes from an OLDER selection; a positive,
        # sign-stable mature cohort with enough observations is mandatory.
        eligible=fully_mature and len(part)>=12 and all(
            p>0 and actual>=0 for p,actual in scenarios
        )
        split=len(part)*2//3
        factor=None
        unadjusted_mae=None
        tentative_holdout_mae=None
        if eligible:
            training=scenarios[:split]
            holdout=scenarios[split:]
            denominator=sum(x for x,_ in training)
            numerator=sum(y for _,y in training)
            if denominator>0 and numerator>0:
                factor=(Decimal(numerator)/Decimal(denominator)).quantize(
                    Decimal(".0001"),rounding=ROUND_HALF_UP)
                if Decimal(".2500")<=factor<=Decimal("4.0000"):
                    unadjusted_mae=sum(abs(y-x) for x,y in holdout)
                    tentative_holdout_mae=sum(
                        abs(Decimal(y)-Decimal(x)*factor)
                        for x,y in holdout
                    )
                else:
                    factor=None
        groups.append({
            "horizon_days":horizon,
            "selected_claimed_cohorts":len(part),
            "fully_mature_claims_present":fully_mature,
            "claimed_aggregate_actual_net_minor":claimed_total if fully_mature else None,
            "forecast_net_total_minor":predicted_total if fully_mature else None,
            "claimed_residual_minor":residual,
            "older_train_count":split if eligible else 0,
            "heldout_test_count":len(part)-split if eligible else 0,
            "illustrative_older_train_ratio_not_production_lambda":(
                str(factor) if factor is not None else None
            ),
            "holdout_raw_mae_minor":(
                str(Decimal(unadjusted_mae)/(len(part)-split))
                if unadjusted_mae is not None else None
            ),
            "holdout_tentative_mae_minor":(
                str((tentative_holdout_mae/(len(part)-split)).quantize(
                    Decimal(".01"),rounding=ROUND_HALF_UP))
                if tentative_holdout_mae is not None else None
            ),
            "production_lambda":None,
            "weight_update_authorized":False,
        })
    transcript=[
        (key,horizon,start.isoformat(),freeze.isoformat(),estimate,actual)
        for key,horizon,start,freeze,estimate,actual in records
    ]
    digest=sha256(json.dumps(
        transcript,sort_keys=True,separators=(",",":"),allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,
        "mode":"OFFLINE_SIMULATION",
        "status":"V421_CLAIMED_RESIDUAL_SENSITIVITY_ONLY_HELD",
        "tenant_id":tenant,
        "currency_code":research_twin["currency_code"],
        "claimed_scenario_count":len(records),
        "missing_claimed_outcomes":missing,
        "immature_cohorts":immature,
        "horizons":groups,
        "scenario_digest_not_bank_attestation":digest,
        "signed_cash_and_negative_margin_supported":True,
        "claimed_bank_outcomes_not_independent_ground_truth":True,
        "complete_six_stage_reconciliation_verified":False,
        "verified_cash_model_calibration":False,
        "live_30_60_90_forecast_activation":False,
        "model_weights_updated":False,
        "training_samples_written":False,
        "economic_memory_written":False,
        "funds_moved":False,
        "paid_traffic_authorized":False,
        "outbound_authorized":False,
        "execution_authority":"none",
    }
