"""V4.21 held dual-direction bank ledger vs buyer advice reconciliation.

Pure offline analysis. Signed statements authenticate to CALLER-SUPPLIED
issuer keys only; they do not prove real bank custody, right to issue keys,
complete original-DB order population or refund finality. No IO or DB writes.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA="empire.predictive_revenue.v421.dual_entry_offline_reconciliation_held.v1"
ORDER_FIELDS=frozenset((
    "order_id","opportunity_id","tenant_id","buyer_id",
    "currency_code","gross_minor","acquisition_cost_minor",
    "accepted_at","source_evidence_digest",
))
ADVICE_FIELDS=frozenset((
    "advice_id","order_id","tenant_id","buyer_id","currency_code",
    "amount_minor","issued_at","evidence_digest","signature_hex",
))
CASH_FIELDS=frozenset((
    "event_id","order_id","tenant_id","currency_code","amount_minor",
    "direction","cleared_at","issuer_id","evidence_digest","signature_hex",
))
MAX_MINOR=10**13
HEX=re.compile(r"^[a-f0-9]{64}$")
SIGNATURE=re.compile(r"^[a-f0-9]{128}$")
ISSUER=re.compile(r"^[a-z0-9_]{3,40}$")


def _check_id(value:object)->str:
    if type(value) is not str or len(value)>50:
        raise ValueError("V421_EXACT_UUID_REQUIRED")
    try:
        raw=UUID(value)
        if str(raw)!=value.lower():
            raise ValueError()
    except (ValueError,AttributeError):
        raise ValueError("V421_CANONICAL_UUID_REQUIRED") from None
    return str(raw)


def _clock(value:object)->datetime:
    if type(value) is not str or len(value)>40:
        raise ValueError("V421_ISO_TIME_REQUIRED")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        if dt.utcoffset() is None:raise ValueError()
        return dt.astimezone(timezone.utc)
    except (ValueError,TypeError):
        raise ValueError("V421_AWARE_ISO_TIME_REQUIRED") from None


def _money(value:object,positive:bool)->int:
    if type(value) is not int or not (0<value<=MAX_MINOR if positive else 0<=value<=MAX_MINOR):
        raise ValueError("V421_INTEGER_MINOR_UNITS_REQUIRED")
    return value


def _digest(value:object)->str:
    if type(value) is not str or HEX.fullmatch(value) is None:
        raise ValueError("V421_SHA256_EVIDENCE_DIGEST_REQUIRED")
    return value


def _canonical_signature_message(row:dict[str,Any])->bytes:
    return json.dumps({k:v for k,v in row.items() if k!="signature_hex"},
                      sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def _check_signature(row:dict[str,Any],key:bytes)->None:
    signature=row["signature_hex"]
    if type(signature) is not str or SIGNATURE.fullmatch(signature) is None:
        raise ValueError("V421_SIGNED_DOCUMENT_REQUIRED")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(
            bytes.fromhex(signature),_canonical_signature_message(row))
    except (InvalidSignature,ValueError,TypeError):
        raise ValueError("V421_INVALID_DOCUMENT_SIGNATURE_HELD") from None


def _keys(keys:object, *, buyers:bool=False)->dict[str,bytes]:
    if type(keys) is not dict or not 1<=len(keys)<=30:
        raise ValueError("V421_EXPLICIT_PINNED_ISSUER_KEYS_REQUIRED")
    for issuer,key in keys.items():
        if type(issuer) is not str or not (
            _valid_uuid(issuer) if buyers else ISSUER.fullmatch(issuer) is not None
        ):
            raise ValueError("V421_BOUNDED_ISSUER_REQUIRED")
        if type(key) is not bytes or len(key)!=32:
            raise ValueError("V421_ED25519_PUBLIC_KEY_REQUIRED")
    return keys


def _valid_uuid(value:str)->bool:
    try:return str(UUID(value))==value
    except ValueError:return False


def reconcile_v421_bilateral_cash_held(
    *,research_twin:dict[str,Any],signed_crm_bearer:str,
    crm_verifier:SignedCrmTenantVerifier,
    original_order_snapshots:tuple[dict[str,Any],...],
    buyer_remittance_advices:tuple[dict[str,Any],...],
    external_bank_events:tuple[dict[str,Any],...],
    pinned_buyer_keys:dict[str,bytes],
    pinned_bank_keys:dict[str,bytes],
    as_of:datetime,
)->dict[str,Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V421_ORIGINAL_NONPROMOTABLE_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V421_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V421_SIGNED_BEARER_REQUIRED")
    if type(as_of) is not datetime or as_of.utcoffset() is None:
        raise ValueError("V421_AWARE_RECONCILIATION_CUTOFF_REQUIRED")
    cutoff=as_of.astimezone(timezone.utc)
    if cutoff>datetime.now(timezone.utc):
        raise ValueError("V421_FUTURE_EVIDENCE_CUTOFF_DENIED")
    if (type(original_order_snapshots) is not tuple
        or type(buyer_remittance_advices) is not tuple
        or type(external_bank_events) is not tuple
        or not 1<=len(original_order_snapshots)<=240
        or len(buyer_remittance_advices)>480
        or len(external_bank_events)>2000):
        raise ValueError("V421_BOUNDED_COMPLETE_SELECTION_REQUIRED")
    buyer_keys=_keys(pinned_buyer_keys,buyers=True)
    bank_keys=_keys(pinned_bank_keys)
    if (set(buyer_keys).intersection(bank_keys)
        or set(buyer_keys.values()).intersection(bank_keys.values())):
        raise ValueError("V421_BANK_AND_BUYER_ISSUERS_MUST_BE_SEPARATE")
    try:tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:raise ValueError("V421_ACTIVE_ORIGINAL_CRM_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V421_CROSS_TENANT_COHORT_DENIED")
    currency=research_twin["currency_code"]

    def bounded_rows(rows:tuple,fields:frozenset,label:str):
        for row in rows:
            if type(row) is not dict or set(row)!=fields:
                raise ValueError("V421_EXACT_"+label+"_FIELDS_REQUIRED")
            if row["tenant_id"]!=tenant:
                raise ValueError("V421_CROSS_TENANT_"+label+"_DENIED")
            if row["currency_code"]!=currency:
                raise ValueError("V421_MIXED_CURRENCY_DENIED")

    bounded_rows(original_order_snapshots,ORDER_FIELDS,"ORDER")
    bounded_rows(buyer_remittance_advices,ADVICE_FIELDS,"ADVICE")
    bounded_rows(external_bank_events,CASH_FIELDS,"BANK")

    orders:dict[str,dict]={}
    for o in original_order_snapshots:
        ident=_check_id(o["order_id"])
        _check_id(o["opportunity_id"])
        _check_id(o["buyer_id"])
        _digest(o["source_evidence_digest"])
        if o["source_evidence_digest"]!=research_twin["source_evidence_digest"]:
            raise ValueError("V421_SOURCE_CUSTODY_DIGEST_MISMATCH")
        _money(o["gross_minor"],True)
        _money(o["acquisition_cost_minor"],False)
        accepted=_clock(o["accepted_at"])
        if accepted>cutoff:
            raise ValueError("V421_FUTURE_ACCEPTED_ORDER")
        if ident in orders:
            raise ValueError("V421_DUPLICATE_CANONICAL_ORDER")
        orders[ident]=o

    advices=defaultdict(list)
    advice_seen=set()
    for a in buyer_remittance_advices:
        _check_id(a["advice_id"])
        ident=_check_id(a["order_id"])
        _check_id(a["buyer_id"])
        _digest(a["evidence_digest"])
        _money(a["amount_minor"],True)
        if a["advice_id"] in advice_seen:
            raise ValueError("V421_DUPLICATE_BUYER_ADVICE")
        advice_seen.add(a["advice_id"])
        if a["buyer_id"] not in buyer_keys:
            raise ValueError("V421_BUYER_ISSUER_KEY_MISSING")
        _check_signature(a,buyer_keys[a["buyer_id"]])
        if _clock(a["issued_at"])>cutoff:
            raise ValueError("V421_FUTURE_BUYER_ADVICE")
        advices[ident].append(a)

    cash=defaultdict(list)
    bank_seen=set()
    for event in external_bank_events:
        _check_id(event["event_id"])
        ident=_check_id(event["order_id"])
        _digest(event["evidence_digest"])
        _money(event["amount_minor"],True)
        if event["direction"] not in ("CREDIT","DEBIT"):
            raise ValueError("V421_BANK_DIRECTION_REQUIRED")
        if event["event_id"] in bank_seen:
            raise ValueError("V421_DUPLICATE_EXTERNAL_BANK_EVENT")
        bank_seen.add(event["event_id"])
        issuer=event["issuer_id"]
        if issuer not in bank_keys:
            raise ValueError("V421_BANK_ISSUER_KEY_MISSING")
        _check_signature(event,bank_keys[issuer])
        if _clock(event["cleared_at"])>cutoff:
            raise ValueError("V421_FUTURE_BANK_TRANSACTION")
        cash[ident].append(event)

    missing_advice=0
    missing_credit=0
    mismatched=0
    candidate_matches=0
    refund_exceeds_credit=0
    gross_total=0
    refunds_total=0
    cost_total=sum(o["acquisition_cost_minor"] for o in orders.values())
    for ident,order in orders.items():
        advice_set=advices.get(ident,[])
        events=cash.get(ident,[])
        credits=[e for e in events if e["direction"]=="CREDIT"]
        debits=[e for e in events if e["direction"]=="DEBIT"]
        credit_total=sum(e["amount_minor"] for e in credits)
        debit_total=sum(e["amount_minor"] for e in debits)
        gross_total+=credit_total
        refunds_total+=debit_total
        if not advice_set:missing_advice+=1
        if not credits:missing_credit+=1
        accepted=_clock(order["accepted_at"])
        advice_consistent=(
            len(advice_set)==1
            and advice_set[0]["buyer_id"]==order["buyer_id"]
            and advice_set[0]["amount_minor"]==order["gross_minor"]
            and _clock(advice_set[0]["issued_at"])>=accepted
        )
        credit_timestamps=[_clock(e["cleared_at"]) for e in credits]
        event_consistent=(
            all(_clock(event["cleared_at"])>=accepted for event in events)
            and all(
                credit_timestamps and
                _clock(debit["cleared_at"])>=min(credit_timestamps)
                for debit in debits
            )
        )
        if debit_total>credit_total:
            refund_exceeds_credit+=1
        matched=(advice_consistent and event_consistent
                 and bool(credits) and credit_total==order["gross_minor"]
                 and debit_total<=credit_total)
        if matched:
            candidate_matches+=1
        else:
            mismatched+=1

    orphans=[ident for ident in (set(advices)|set(cash)) if ident not in orders]
    unknown_credit=sum(
        event["direction"]=="CREDIT" for ident in orphans for event in cash[ident]
    )
    unknown_debit=sum(
        event["direction"]=="DEBIT" for ident in orphans for event in cash[ident]
    )
    horizons=[]
    for days in (30,60,90):
        fully_mature=all(_clock(o["accepted_at"])+timedelta(days=days)<=cutoff
                         for o in orders.values())
        claimed_net=None
        observed_credit=None
        observed_refund=None
        if fully_mature:
            observed_credit=sum(
                e["amount_minor"] for ident in orders for e in cash.get(ident,[])
                if e["direction"]=="CREDIT"
                and _clock(e["cleared_at"])<=_clock(orders[ident]["accepted_at"])+timedelta(days=days)
            )
            observed_refund=sum(
                e["amount_minor"] for ident in orders for e in cash.get(ident,[])
                if e["direction"]=="DEBIT"
                and _clock(e["cleared_at"])<=_clock(orders[ident]["accepted_at"])+timedelta(days=days)
            )
            claimed_net=observed_credit-observed_refund-cost_total
        horizons.append({
            "horizon_days":days,
            "all_selected_orders_mature":fully_mature,
            "claimed_credit_within_horizon_minor":observed_credit,
            "claimed_refund_within_horizon_minor":observed_refund,
            "illustrative_net_within_horizon_minor":claimed_net,
            "bank_verified_cash_minor":None,
            "eligible_for_production_calibration":False,
        })
    transcript=sha256(json.dumps({
        "orders":original_order_snapshots,
        "buyer_advices":buyer_remittance_advices,
        "external_bank_events":external_bank_events,
    },sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    fully_reconciled_claimed=(
        candidate_matches==len(orders)
        and not orphans
        and unknown_credit==0 and unknown_debit==0
        and refund_exceeds_credit==0
    )
    return {
        "schema_version":SCHEMA,"status":"V421_TWO_WAY_SIGNED_CLAIMS_ONLY_HELD",
        "mode":"OFFLINE_SIMULATION",
        "canonical_tenant_id":tenant,"currency_code":currency,
        "earliest_selected_order_accepted_at_utc":min(
            _clock(o["accepted_at"]) for o in orders.values()
        ).isoformat(),
        "order_rows_selected":len(orders),
        "buyer_advice_rows_selected":len(buyer_remittance_advices),
        "external_bank_events_selected":len(external_bank_events),
        "matched_order_claims":candidate_matches,
        "orders_with_missing_buyer_advice":missing_advice,
        "orders_with_missing_bank_credit":missing_credit,
        "orders_with_discrepancy":mismatched,
        "orphan_external_order_references":len(orphans),
        "orphan_external_credit_events":unknown_credit,
        "orphan_external_debit_events":unknown_debit,
        "refunds_exceed_credit_orders":refund_exceeds_credit,
        "claimed_gross_credit_minor":gross_total,
        "claimed_refund_or_clawback_minor":refunds_total,
        "claimed_acquisition_cost_minor":cost_total,
        "illustrative_net_minor":gross_total-refunds_total-cost_total,
        "all_supplied_claims_reconciled":fully_reconciled_claimed,
        "signature_valid_against_caller_supplied_keys":True,
        "caller_pinned_key_authority_independently_verified":False,
        "original_empiredb_order_snapshot_independently_attested":False,
        "external_bank_population_complete_verified":False,
        "actual_bank_settlement_independently_verified":False,
        "refund_chargeback_finality_verified":False,
        "source_rights_independently_verified":False,
        "original_opportunity_denominator_complete_verified":False,
        "horizons":horizons,
        "source_manifest_digest_not_bank_proof":transcript,
        "training_examples_eligible":0,
        "model_weights_updated":False,
        "production_calibration_authorized":False,
        "actual_realised_net_cash_minor":None,
        "economic_memory_written":False,
        "outbound_authorized":False,
        "paid_traffic_authorized":False,
        "funds_moved":False,
        "execution_authority":"none",
    }



def review_v421_two_way_forecast_residuals_held(
    *, claimed_reconciliation:dict[str,Any],
    frozen_forecasts:tuple[dict[str,Any],...],
    research_twin:dict[str,Any],
    signed_crm_bearer:str,crm_verifier:SignedCrmTenantVerifier,
)->dict[str,Any]:
    """Join signed-claim horizons to frozen forecasts, never model training."""
    if not _original_twin_contract(research_twin):
        raise ValueError("V421_ORIGINAL_SIMULATION_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V421_ORIGINAL_CRM_VERIFIER_REQUIRED")
    try:tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:raise ValueError("V421_ACTIVE_SIGNED_CRM_REQUIRED") from None
    if (type(claimed_reconciliation) is not dict
        or claimed_reconciliation.get("schema_version")!=SCHEMA
        or claimed_reconciliation.get("status")!="V421_TWO_WAY_SIGNED_CLAIMS_ONLY_HELD"
        or claimed_reconciliation.get("canonical_tenant_id")!=tenant
        or tenant!=research_twin["canonical_tenant_id"]
        or claimed_reconciliation.get("currency_code")!=research_twin["currency_code"]
        or claimed_reconciliation.get("actual_realised_net_cash_minor") is not None
        or claimed_reconciliation.get("production_calibration_authorized") is not False
        or claimed_reconciliation.get("model_weights_updated") is not False
        or claimed_reconciliation.get("execution_authority")!="none"):
        raise ValueError("V421_NONPROMOTABLE_RECONCILIATION_REQUIRED")
    if type(frozen_forecasts) is not tuple or len(frozen_forecasts)!=3:
        raise ValueError("V421_THREE_LOCKED_HORIZON_FORECASTS_REQUIRED")
    claimed_horizons=claimed_reconciliation.get("horizons")
    if (type(claimed_horizons) is not list or len(claimed_horizons)!=3
        or [r.get("horizon_days") for r in claimed_horizons]!=[30,60,90]):
        raise ValueError("V421_ORIGINAL_CASH_HORIZONS_REQUIRED")
    digest=claimed_reconciliation.get("source_manifest_digest_not_bank_proof")
    if type(digest) is not str or HEX.fullmatch(digest) is None:
        raise ValueError("V421_CLAIM_MANIFEST_DIGEST_REQUIRED")
    inception=_clock(claimed_reconciliation["earliest_selected_order_accepted_at_utc"])
    seen=set()
    residuals={}
    for record in frozen_forecasts:
        if (type(record) is not dict or set(record)!={
            "horizon_days","forecast_net_minor","locked_at","reconciliation_manifest_digest"
        }):
            raise ValueError("V421_FROZEN_FORECAST_FIELDS_REQUIRED")
        horizon=record["horizon_days"]
        forecast=record["forecast_net_minor"]
        if type(horizon) is not int or horizon not in (30,60,90) or horizon in seen:
            raise ValueError("V421_UNIQUE_30_60_90_FORECASTS_REQUIRED")
        seen.add(horizon)
        if (type(forecast) is not int or not -MAX_MINOR<=forecast<=MAX_MINOR
            or record["reconciliation_manifest_digest"]!=digest
            or _clock(record["locked_at"])>=inception):
            raise ValueError("V421_FROZEN_BEFORE_COHORT_MANIFEST_REQUIRED")
        stage=claimed_horizons[[30,60,90].index(horizon)]
        if (stage["bank_verified_cash_minor"] is not None
            or stage["eligible_for_production_calibration"] is not False):
            raise ValueError("V421_FORGED_BANK_AUTHORITY_DENIED")
        claimed=stage["illustrative_net_within_horizon_minor"]
        if claimed is not None and (type(claimed) is not int or abs(claimed)>MAX_MINOR*1000):
            raise ValueError("V421_SIGNED_CASH_MINOR_REQUIRED")
        residuals[horizon]={
            "horizon_days":horizon,
            "frozen_forecast_minor":forecast,
            "claimed_net_minor":claimed,
            "claimed_residual_minor":claimed-forecast if claimed is not None else None,
            "bank_settled_outcome_verified":False,
            "production_calibration_ratio":None,
        }
    return {
        "status":"V421_DUAL_ENTRY_RESIDUAL_COMPARISON_HELD",
        "mode":"OFFLINE_SIMULATION",
        "canonical_tenant_id":tenant,
        "currency_code":research_twin["currency_code"],
        "manifest_digest_not_financial_attestation":digest,
        "horizons":[residuals[n] for n in (30,60,90)],
        "historical_predictions_frozen_proven_independently":False,
        "cash_ground_truth_verified":False,
        "historical_learning_eligible":False,
        "model_weights_updated":False,
        "production_forecasting_authorized":False,
        "economic_memory_written":False,
        "funds_moved":False,
        "execution_authority":"none",
    }
