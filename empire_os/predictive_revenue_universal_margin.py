"""Original EmpireOS Predictive Revenue v3: canonical economics and net-yield council.

A deterministic, owner-review-only research engine. It NEVER transfers calls,
dispatches contractors, changes advertising budgets, throttles a live channel,
writes to EmpireDB, invoices or settles money.

All inputs are untrusted caller-supplied research/test evidence. An attestation
flag is a processing prerequisite, NOT independent payment/source verification.
Amounts are integer currency minor units; no unapproved FX conversions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json,re

SCHEMA="empire.original-predictive-revenue-universal-margin.v3.observe"
ROUTER_SCHEMA="empire.original-predictive-revenue-net-yield-router.v3.observe"
SECTORS=frozenset({
    "PAY_PER_CALL","HOME_SERVICES","ECOMMERCE","SAAS_USAGE","NATIVE_ADS",
})
COSTS=(
    "acquisition_minor","fulfillment_minor","overhead_minor",
    "processing_minor","refunds_minor","other_cost_minor",
)
REQUIRED_EVENT={
    "event_id","niche_type","entity_id","tenant_scope","timestamp_utc",
    "currency","raw_volume","qualified_units","gross_collected_minor",
    "costs","settlement_owner_attested","fulfillment_owner_attested",
    "source_owner_attested","evidence_basis","source_receipt_fingerprint",
}
REQUIRED_DEST={
    "destination_id","sector","currency","geography","payout_minor",
    "per_attempt_incremental_minor","per_qualified_fulfillment_minor",
    "per_qualified_processing_minor","attempts_observed",
    "qualified_observed","daily_cap","daily_used","source_cost_owner_attested",
    "buyer_payout_owner_attested","route_terms_owner_attested",
    "source_rights_owner_attested","destination_operationally_available",
    "traffic_source",
}
BASE_ACTION_FLAGS={
    "queue_or_transport_invoked":False,
    "call_or_lead_transferred":False,
    "paid_campaign_budget_changed":False,
    "contractor_dispatched":False,
    "subscription_changed":False,
    "db_or_crm_mutation":False,
    "payment_moved":False,
    "execution_authority":"none",
}


def _canonical_hash(value:Any)->str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
                             allow_nan=False).encode()).hexdigest()


def _nonnegative_int(v:Any,name:str)->int:
    if type(v) is not int or v<0 or v>10**15:
        raise ValueError("margin_"+name+"_must_be_nonnegative_integer_minor_units")
    return v


def _positive_int(v:Any,name:str)->int:
    n=_nonnegative_int(v,name)
    if n==0:raise ValueError("margin_"+name+"_must_be_positive")
    return n


def _string(v:Any,name:str,pattern:str)->str:
    if not isinstance(v,str) or not re.fullmatch(pattern,v):
        raise ValueError("margin_"+name+"_invalid")
    return v


def _utc(v:Any)->datetime:
    if not isinstance(v,str):
        raise ValueError("margin_timestamp_required")
    try:
        stamp=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("margin_timestamp_invalid") from exc
    if stamp.utcoffset() is None:
        raise ValueError("margin_timestamp_timezone_required")
    return stamp.astimezone(timezone.utc)


def _flag(v:Any,name:str)->bool:
    if type(v) is not bool:
        raise ValueError("margin_"+name+"_must_be_boolean")
    return v


def normalize_universal_margin_event(row:Mapping[str,Any])->dict:
    """Normalize single-sector money WITHOUT mislabelling synthetic as realised."""
    if not isinstance(row,Mapping) or set(row)!=REQUIRED_EVENT:
        raise ValueError("margin_event_exact_schema_required")
    eid=_string(row["event_id"],"event_id",r"[A-Za-z0-9][A-Za-z0-9:_-]{4,100}")
    sector=row["niche_type"]
    if sector not in SECTORS:
        raise ValueError("margin_event_sector_unknown")
    tenant=_string(row["tenant_scope"],"tenant_scope",r"[a-z][a-z0-9_.:-]{2,100}")
    entity=_string(row["entity_id"],"entity_id",r"[A-Za-z0-9][A-Za-z0-9:_-]{2,100}")
    currency=_string(row["currency"],"currency",r"[A-Z]{3}")
    at=_utc(row["timestamp_utc"])
    volume=_nonnegative_int(row["raw_volume"],"raw_volume")
    qualified=_nonnegative_int(row["qualified_units"],"qualified_units")
    if qualified>volume:
        raise ValueError("margin_qualified_units_exceed_raw_volume")
    gross=_nonnegative_int(row["gross_collected_minor"],"gross_collected")
    costs=row["costs"]
    if not isinstance(costs,Mapping) or set(costs)!=set(COSTS):
        raise ValueError("margin_exact_cost_categories_required")
    values={k:_nonnegative_int(costs[k],k) for k in COSTS}
    # Acquisition/overhead/costs are already event TOTALS; never multiply by
    # qualified units or apply a conversion rate to realised gross.
    total_cost=sum(values.values())
    owner_flags={k:_flag(row[k],k) for k in (
        "settlement_owner_attested","fulfillment_owner_attested",
        "source_owner_attested",
    )}
    basis=row["evidence_basis"]
    if basis not in {"SYNTHETIC","UNRECONCILED","OWNER_ATTESTED"}:
        raise ValueError("margin_evidence_basis_unknown")
    receipt=row["source_receipt_fingerprint"]
    if receipt is not None:
        _string(receipt,"receipt",r"[0-9a-f]{64}")
    if basis=="OWNER_ATTESTED" and (not all(owner_flags.values()) or receipt is None):
        raise ValueError("margin_owner_attestation_or_receipt_missing")
    if basis=="SYNTHETIC" and (any(owner_flags.values()) or receipt is not None):
        raise ValueError("margin_synthetic_cannot_claim_source_attestation")
    # Verified receipts require original owner systems outside this module.
    # Never elevate mere input flags to "actual revenue verified".
    classified="SYNTHETIC" if basis=="SYNTHETIC" else "UNVERIFIED_INPUT"
    result={
        "schema_version":SCHEMA,"event_id":eid,
        "niche_type":sector,"entity_id":entity,"tenant_scope":tenant,
        "timestamp_utc":at.isoformat(),"currency":currency,
        "raw_volume":volume,"qualified_units":qualified,
        "gross_collected_minor_input":gross,
        "cost_breakdown_minor":values,
        "cost_total_minor_input":total_cost,
        "contribution_minor_input":gross-total_cost,
        "evidence_classification":classified,
        "separately_authenticated_revenue_truth":False,
        "finance_and_fulfillment_original_receipts_independently_verified":False,
        "ready_for_canonical_ledger_admission":False,
        "cash_received_verified_here":False,
        "original_receipt_reference_fingerprint":receipt,
        "external_system_mutations":False,
    }
    result["record_sha256"]=_canonical_hash(result)
    return result


def _decimal_money(v:Decimal)->str:
    return format(v.quantize(Decimal("0.0001"),rounding=ROUND_HALF_EVEN),".4f")


def evaluate_net_yield_council(
    *,request_id:str,tenant_scope:str,niche_type:str,
    currency:str,geography:str,traffic_source:str,
    destinations:Sequence[Mapping[str,Any]],min_positive_yield_minor:int=0,
    minimum_observations:int=30,
)->dict:
    """Abstaining net-yield decision support; NEVER an executable routing plan.

    Expected per inbound: success probability ×
    (payout - conditional fulfillment - processing) - incremental cost.
    Historical qualification rate must be a bounded measured sample.
    Daily cap zero, bad source rights and no-paid-traffic block candidates.
    """
    request=_string(request_id,"request_id",r"[A-Za-z0-9][A-Za-z0-9:_-]{4,100}")
    tenant=_string(tenant_scope,"tenant_scope",r"[a-z][a-z0-9_.:-]{2,100}")
    if niche_type not in SECTORS:
        raise ValueError("margin_request_sector_unknown")
    cur=_string(currency,"currency",r"[A-Z]{3}")
    geo=_string(geography,"geography",r"[A-Z]{2}(?:-[A-Z0-9]{1,8})?")
    traffic=_string(traffic_source,"traffic_source",r"[A-Z_]{3,32}")
    threshold=_nonnegative_int(min_positive_yield_minor,"minimum_yield")
    min_obs=_positive_int(minimum_observations,"minimum_observations")
    if min_obs<30:
        raise ValueError("margin_minimum_observations_cannot_be_below_30")
    if not isinstance(destinations,(list,tuple)) or len(destinations)>100:
        raise ValueError("margin_bounded_destination_list_required")
    if len(destinations)==0:
        raise ValueError("margin_at_least_one_destination_required")
    outputs=[]
    ids=set()
    for entry in destinations:
        if not isinstance(entry,Mapping) or set(entry)!=REQUIRED_DEST:
            raise ValueError("margin_destination_exact_schema_required")
        dest=_string(entry["destination_id"],"destination",r"[A-Za-z0-9][A-Za-z0-9:_-]{2,100}")
        if dest in ids:raise ValueError("margin_duplicate_destination_id")
        ids.add(dest)
        reasons=[]
        for name in (
            "source_cost_owner_attested","buyer_payout_owner_attested",
            "route_terms_owner_attested","source_rights_owner_attested",
            "destination_operationally_available",
        ):
            _flag(entry[name],name)
            if entry[name] is not True:reasons.append(name+"_missing")
        if entry["sector"]!=niche_type:reasons.append("sector_mismatch")
        if entry["currency"]!=cur:reasons.append("currency_mismatch_no_fx")
        if entry["geography"]!=geo:reasons.append("geography_mismatch")
        if entry["traffic_source"]!=traffic:
            reasons.append("traffic_source_mismatch")
        if traffic not in {"ORGANIC","OWNED","REFERRAL","INBOUND"}:
            reasons.append("paid_or_unapproved_traffic_prohibited")
        payout=_nonnegative_int(entry["payout_minor"],"payout")
        attempt_cost=_nonnegative_int(entry["per_attempt_incremental_minor"],"incremental_cost")
        qualified_cost=_nonnegative_int(entry["per_qualified_fulfillment_minor"],"fulfillment")
        processing=_nonnegative_int(entry["per_qualified_processing_minor"],"processing")
        attempts=_nonnegative_int(entry["attempts_observed"],"attempts")
        success=_nonnegative_int(entry["qualified_observed"],"qualified")
        cap=_positive_int(entry["daily_cap"],"daily_cap")
        used=_nonnegative_int(entry["daily_used"],"daily_used")
        if used>cap:raise ValueError("margin_cap_usage_exceeds_daily_cap")
        if success>attempts:raise ValueError("margin_conversion_numerator_exceeds_denominator")
        if attempts<min_obs:reasons.append("historical_sample_below_threshold")
        if cap-used==0:reasons.append("capacity_cap_exhausted")
        if payout<=qualified_cost+processing:
            reasons.append("nonpositive_success_contribution")
        p=(Decimal(success)/Decimal(attempts)) if attempts else None
        expected=None
        if p is not None:
            expected=p*Decimal(payout-qualified_cost-processing)-Decimal(attempt_cost)
            if expected<=Decimal(threshold):
                reasons.append("expected_contribution_below_threshold")
        outputs.append({
            "destination_id":dest,
            "source_sample_attempts":attempts,
            "source_sample_qualified":success,
            "historical_qualification_rate_observed":(
                _decimal_money(p) if p is not None else None
            ),
            "daily_cap_remaining":cap-used,
            "incremental_cost_minor":attempt_cost,
            "conditional_cost_minor":qualified_cost+processing,
            "expected_net_yield_minor":(
                _decimal_money(expected) if expected is not None else None
            ),
            "eligible_for_human_routing_review":len(reasons)==0,
            "blockers":sorted(set(reasons)),
        })
    # A financial opportunity is not real merely because a model says so.
    eligible=sorted(
        (r for r in outputs if r["eligible_for_human_routing_review"]),
        key=lambda r:(-Decimal(r["expected_net_yield_minor"]),r["destination_id"]),
    )
    winner=eligible[0] if eligible else None
    result={
        "schema_version":ROUTER_SCHEMA,"mode":"OBSERVE",
        "request_id":request,"tenant_scope":tenant,"niche_type":niche_type,
        "currency":cur,"geography":geo,"traffic_source":traffic,
        "candidate_count":len(outputs),
        "historical_sample_minimum":min_obs,
        "minimum_positive_expected_yield_minor":threshold,
        "candidate_evaluations":sorted(outputs,key=lambda r:r["destination_id"]),
        "proposed_best_destination_for_owner_review":(
            winner["destination_id"] if winner else None
        ),
        "proposed_expected_yield_minor":(
            winner["expected_net_yield_minor"] if winner else None
        ),
        "decision":(
            "CANDIDATE_FOR_INDEPENDENT_OWNER_REVIEW"
            if winner else "HOLD_NO_SAFE_VERIFIED_DESTINATION"
        ),
        "unverified_rate_not_predictive_skill":True,
        "no_paid_traffic_policy":True,
        "no_automatic_fallback_to_unverified_provider":True,
        "real_route_authorization":False,
        "independent_original_buyer_rights_or_payout_receipts_checked_here":False,
        **BASE_ACTION_FLAGS,
    }
    result["snapshot_sha256"]=_canonical_hash(result)
    return result
