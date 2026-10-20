"""Source-scoped commercial funnel stagnation diagnostic for Predictive Revenue.

The original Founder Funnel contains global stage counters, not attributable
closed cohorts. Never subtract adjacent counters to invent conversion, denied
buying demand, money left on the table, or causal reasons.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.commercial_funnel import _commercial_stage
from empire_os.predictive_customer_value_demand import _time

SCHEMA="empire.predictive_revenue.commercial_funnel_gap_instrument.v1"
SOURCE_SCHEMA="empire.founder_commercial_funnel.v1"
SOURCE_REL="runtime/commercial_funnel/latest.json"
MAX_BYTES=500_000
RECENCY=timedelta(hours=48)
STAGES=(
    "prospect_acquisitions","buyer_reviews","buyer_reviews_approved",
    "outbound_intents","outbound_delivered","commercial_replies",
    "closer_cases","commercial_terms_reviews","commercial_terms_approved",
    "payment_requests","verified_payment_evidence","fulfilment_orders",
    "fulfilled_orders","recognized_revenue_events",
)


def _hold(status:str,source_age_hours:float|None=None)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,"status":status,
        "mode":"OBSERVE","source_age_hours":source_age_hours,
        "source_observed_at":None,"source_revision_sha256":None,
        "source_reported_stage_counts":None,
        "source_owner_stage":None,"source_owner_next_event":None,
        "stagnation_hypothesis_code":None,
        "stage_counts_share_a_verified_purchase_cohort":False,
        "stage_counts_allow_conversion_fractions":False,
        "derived_revenue_lost_minor":None,
        "independent_buyer_purchase_authenticated":False,
        "recognized_profit_by_cohort_minor":None,
        "root_cause_established":False,
        "next_evidence_owner":None,"next_action":None,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }


def review_commercial_funnel_gap_source(
    owner:Mapping[str,Any]|None, *, as_of:datetime,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware decision clock required")
    if owner is None:
        return _hold("FOUNDER_FUNNEL_SOURCE_MISSING")
    if (not isinstance(owner,Mapping)
            or owner.get("schema_version")!=SOURCE_SCHEMA
            or owner.get("mode")!="OBSERVE"
            or owner.get("execution_authority")!="none"
            or type(owner.get("actual_revenue")) is not bool
            or type(owner.get("recognized_revenue_cents")) is not int
            or type(owner.get("realized_margin_cents")) is not int):
        return _hold("FOUNDER_FUNNEL_SOURCE_CONTRACT_HOLD")
    try:
        epoch=_time(owner.get("generated_at"))
    except ValueError:
        return _hold("FOUNDER_FUNNEL_SOURCE_TIME_HOLD")
    age=as_of.astimezone(timezone.utc)-epoch
    if age<timedelta(0):
        return _hold("FOUNDER_FUNNEL_SOURCE_TIME_HOLD")
    if age>RECENCY:
        return _hold(
            "FOUNDER_FUNNEL_SOURCE_STALE_HOLD",
            source_age_hours=round(age.total_seconds()/3600,3),
        )
    counts=owner.get("counts")
    if (not isinstance(counts,Mapping)
            or any(type(counts.get(k)) is not int or not 0<=counts[k]<=100_000_000
                   for k in STAGES)
            or any(not isinstance(k,str) or len(k)>100
                   for k in counts)):
        return _hold("FOUNDER_FUNNEL_COUNTS_HOLD")
    state,next_step=_commercial_stage(counts)
    if owner.get("current_stage")!=state or owner.get("next_event")!=next_step:
        return _hold("FOUNDER_FUNNEL_STAGE_CONFLICT_HOLD")
    observed={k:counts[k] for k in STAGES}
    if counts["outbound_delivered"]>0 and counts["commercial_replies"]==0:
        hypothesis="DELIVERED_OUTBOUND_WITH_NO_REPLIES_RECORDED_IN_SOURCE"
        action="CHECK_ORIGINAL_PROVIDER_REPLY_BINDING_DELIVERY_AND_COHORT_WINDOW"
        next_owner="existing_provider_reply_attribution_and_buyer_crm_owner"
    elif counts["commercial_replies"]>0 and counts["commercial_terms_approved"]==0:
        hypothesis="REPLIES_WITH_NO_APPROVED_TERMS_RECORDED_IN_SOURCE"
        action="VERIFY_ORIGINAL_BUYING_ROLE_FIT_AND_COMMERCIAL_TERMS"
        next_owner="existing_sales_qualifier_and_commercial_terms_owner"
    elif counts["commercial_terms_approved"]>0 and counts["verified_payment_evidence"]==0:
        hypothesis="APPROVED_TERMS_WITH_NO_VERIFIED_PAYMENT_IN_SOURCE"
        action="REVIEW_SIGNED_TERMS_PAYMENT_PROVIDER_AND_SETTLEMENT"
        next_owner="existing_billing_and_commerce_owner"
    else:
        hypothesis="NO_SINGLE_STAGE_STAGNATION_CLAIM_FROM_AVAILABLE_COUNTS"
        action="CHECK_SOURCE_COHORT_AND_PERIOD_BEFORE_GAP_CAUSAL_ANALYSIS"
        next_owner="existing_commercial_funnel_and_source_owner"
    digest=sha256(json.dumps({
        "epoch":epoch.isoformat(),
        "observed_stage_counts":observed,
        "status":state,
    },sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        **_hold("FOUNDER_FUNNEL_AGGREGATE_STAGE_RESEARCH_REVIEWED"),
        "source_observed_at":epoch.isoformat(),
        "source_age_hours":round(age.total_seconds()/3600,3),
        "source_revision_sha256":digest,
        "source_reported_stage_counts":observed,
        "source_owner_stage":state,
        "source_owner_next_event":next_step,
        "stagnation_hypothesis_code":hypothesis,
        "next_evidence_owner":next_owner,
        "next_action":action,
        "owner_reporting_window_and_event_linkage_independently_verified":False,
        "observed_zero_replies_proves_no_industry_buying_demand":False,
        "source_revenue_total_can_be_attributed_to_proposed_gap":False,
        "cause_of_stagnation_verified":False,
        "original_provider_and_tenant_binding_required":True,
    }


def review_commercial_funnel_gap_runtime(
    repo_root:str|Path, *, as_of:datetime,
)->dict[str,Any]:
    root=Path(repo_root).resolve()
    path=root/SOURCE_REL
    try:
        if (path.is_symlink() or path.parent.is_symlink()
                or (root/"runtime").is_symlink()
                or not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES):
            return _hold("FOUNDER_FUNNEL_SOURCE_MISSING")
        source=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        return _hold("FOUNDER_FUNNEL_SOURCE_UNREADABLE")
    return review_commercial_funnel_gap_source(source,as_of=as_of)
