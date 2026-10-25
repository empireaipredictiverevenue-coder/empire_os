"""V4.21 bounded original-tenant six-stage reconciliation, strictly HELD.

Combines V4.20 and V4.21 original EmpireDB read functions in one snapshot.
Balances are self-declared claims, never final bank cash or model truth.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
from typing import Any,Callable

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v415_direct_cash_reader import CAPABILITY_ROLE,READER_LOGIN
from empire_os.predictive_revenue_v420_three_pillar_audit import SQL as V420_SQL,CHANNEL
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA="empire.predictive_revenue.v421.six_stage_lifecycle_held.v1"
SQL=(
 "SELECT opportunity_count,claimed_authorized_inbound_count,"
 "event_covered_opportunity_count,accepted_order_opportunity_count,"
 "paired_clearing_opportunity_count,unmatched_or_discrepant_finance_opportunity_count,"
 "refund_or_clawback_claimed_order_count,refund_or_clawback_claim_count,"
 "claimed_gross_clearing_minor,claimed_refund_clawback_minor,"
 "claimed_acquisition_cost_minor,illustrative_net_after_claims_minor,"
 "complete_upstream_census_verified,independently_verified_source_rights,"
 "bank_settlement_finality_verified,refunds_and_chargebacks_complete_verified,"
 "realized_net_cash_verified,forecast_retraining_authorized "
 "FROM public.read_predictive_revenue_lifecycle_held_v421("
 "%s::uuid,%s::text,%s::timestamptz,%s::timestamptz)"
)

def review_v421_six_stage_held(
    *,research_twin:dict[str,Any],signed_crm_bearer:str,
    crm_verifier:SignedCrmTenantVerifier,channel_name:str,
    window_start:datetime,window_end:datetime,
    dedicated_cash_dsn:str,connect_factory:Callable|None=None,
)->dict[str,Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V421_NONPROMOTABLE_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V421_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V421_SIGNED_CRM_BEARER_REQUIRED")
    if type(channel_name) is not str or not CHANNEL.fullmatch(channel_name):
        raise ValueError("V421_SCOPED_CHANNEL_REQUIRED")
    if (type(window_start) is not datetime or type(window_end) is not datetime
        or window_start.utcoffset() is None or window_end.utcoffset() is None):
        raise ValueError("V421_TZ_AWARE_WINDOW_REQUIRED")
    start,end=window_start.astimezone(timezone.utc),window_end.astimezone(timezone.utc)
    now=datetime.now(timezone.utc)
    if not (timedelta(0)<end-start<=timedelta(days=31)
            and end<=now and start>=now-timedelta(days=365*5+2)):
        raise ValueError("V421_BOUNDED_WINDOW_REQUIRED")
    if type(dedicated_cash_dsn) is not str or not 1<=len(dedicated_cash_dsn.strip())<=4096:
        raise ValueError("V421_DEDICATED_READER_DSN_REQUIRED")
    try:
        tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V421_ACTIVE_SIGNED_CRM_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V421_CRM_TENANT_MISMATCH")
    original=connect_factory is None

    def held(status:str, values:tuple|None=None)->dict[str,Any]:
        nums=values if values is not None else (None,)*12
        (total,source,event,orders,clearing,conflicting,refunded_orders,
         refunds,gross,clawback,spent,illustrative)=nums
        return {
            "schema_version":SCHEMA,"mode":"OBSERVE","status":status,
            "canonical_tenant_id":tenant,"channel_name":channel_name,
            "window_start_utc":start.isoformat(),"window_end_utc":end.isoformat(),
            "original_postgresql_connector_used":original,
            "database_endpoint_attested":False,
            "snapshot_isolation":"REPEATABLE_READ",
            "stage_1_claimed_authorized_inbound":source,
            "stage_2_claimed_opportunity_denominator":total,
            "stage_2_claimed_event_coverage":event,
            "stage_3_opportunities_with_accepted_order":orders,
            "stage_4_opportunities_with_paired_clearing_claim":clearing,
            "stage_4_discrepancy_opportunity_count":conflicting,
            "stage_5_orders_with_refund_or_clawback_claim":refunded_orders,
            "stage_5_refund_or_clawback_claim_count":refunds,
            "claimed_gross_clearing_minor":gross,
            "claimed_refund_clawback_minor":clawback,
            "claimed_acquisition_spend_minor":spent,
            "illustrative_net_after_claims_minor":illustrative,
            "claim_is_not_independent_bank_finality":True,
            "refund_census_complete_verified":False,
            "original_inbound_event_census_complete_verified":False,
            "source_licensing_independently_verified":False,
            "realised_net_cash_verified_minor":None,
            "cash_baseline_verified_for_training":False,
            "residual_feedback_release_authorized":False,
            "calibrated_30_60_90_forecasts":None,
            "model_weights_updated":False,
            "economic_memory_written":False,
            "paid_traffic_authorized":False,
            "outbound_authorized":False,
            "money_movement_authorized":False,
            "execution_authority":"none",
        }
    if original:
        try:
            import psycopg
            connect_factory=psycopg.connect
        except ImportError:
            return held("V421_RESTRICTED_READER_UNAVAILABLE_HELD")
    try:
        with connect_factory(dedicated_cash_dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                cur.execute("SET LOCAL ROLE "+CAPABILITY_ROLE)
                cur.execute("SELECT session_user,current_user")
                if cur.fetchone()!=(READER_LOGIN,CAPABILITY_ROLE):
                    return held("V421_ORIGINAL_READER_IDENTITY_INVALID_HELD")
                args=(tenant,channel_name,start,end)
                cur.execute(V420_SQL,args)
                prior=cur.fetchall()
                cur.execute(SQL,args)
                result=cur.fetchall()
        if (type(prior) is not list or len(prior)!=1
            or type(prior[0]) not in (tuple,list) or len(prior[0])!=16
            or type(result) is not list or len(result)!=1
            or type(result[0]) not in (tuple,list) or len(result[0])!=18):
            return held("V421_INCOMPLETE_LIFECYCLE_JOIN_HELD")
        older,current=prior[0],result[0]
        basic=current[:8]
        financial=current[8:12]
        if (any(type(x) is not int or not 0<=x<=5000 for x in older[:8])
            or older[2]>older[1] or older[4]>older[2]
            or older[4]>older[3] or older[6]>older[5]
            or any(x is not False for x in older[10:])):
            return held("V421_PRIOR_COVERAGE_NOT_TRUSTED_HELD")
        if (any(type(x) is not int or not 0<=x<=5000 for x in basic)
            or basic[0]!=older[0] or basic[1]!=older[2]
            or basic[2]!=older[4] or basic[3]!=older[5]
            or basic[4]!=older[6] or basic[5]!=older[7]
            or basic[4]>basic[3] or basic[6]>basic[7]
            or type(financial[0]) not in (Decimal,int)
            or type(financial[1]) not in (Decimal,int)
            or type(financial[2]) not in (Decimal,int)
            or type(financial[3]) not in (Decimal,int)
            or any(abs(x)>10**15 or x!=int(x) for x in financial)
            or any(x<0 for x in financial[:3])
            or any(x is not False for x in current[12:])
            or financial[3]!=financial[0]-financial[1]-financial[2]):
            return held("V421_UNTRUSTED_LIFECYCLE_OR_CASH_PROMOTION_HELD")
        if not original:
            return held("V421_INJECTED_CONNECTOR_NOT_PROOF_HELD")
        return held("V421_SIX_STAGE_CLAIMED_LIFECYCLE_ONLY_HELD",
                    tuple(basic)+tuple(int(x) for x in financial))
    except Exception:
        return held("V421_RESTRICTED_READER_UNAVAILABLE_HELD")
