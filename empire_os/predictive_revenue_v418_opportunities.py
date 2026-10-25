"""Empire Predictive Revenue V4.18: tenant opportunity custody census (HELD).

Reuses original EmpireDB gtm_opportunities and fulfilment_orders, signed Smart
CRM, and the established restricted read-only login. No DB migration occurs
from this module. A custody CLAIM is never independent source permission or
a complete all-channel opportunity census.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v415_direct_cash_reader import READER_LOGIN, CAPABILITY_ROLE
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v418.gtm_opportunity_custody_held.v1"
SQL = (
    "SELECT custody_count,open_count,disqualified_count,dead_count,"
    "converted_claim_count,converted_with_tenant_order_count,"
    "missing_state_evidence_count,unlinked_converted_count,"
    "acquisition_cost_minor_sum,mixed_currency_count,cohort_currency_code,"
    "opportunity_population_complete_verified,customer_cvr_verified,"
    "finance_cash_matched,model_calibration_authorized "
    "FROM public.read_predictive_revenue_gtm_denominator_v418("
    "%s::uuid,%s::timestamptz,%s::timestamptz)"
)


def review_v418_opportunity_custody_held(
    *, research_twin: dict[str, Any],
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    window_start: datetime,
    window_end: datetime,
    dedicated_cash_dsn: str,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V418_ORIGINAL_NO_EXECUTION_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V418_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V418_ORIGINAL_SIGNED_CRM_BEARER_REQUIRED")
    if (type(window_start) is not datetime or type(window_end) is not datetime
        or window_start.tzinfo is None or window_end.tzinfo is None
        or window_start.utcoffset() is None or window_end.utcoffset() is None):
        raise ValueError("V418_TIMEZONE_AWARE_WINDOW_REQUIRED")
    start,end = window_start.astimezone(timezone.utc),window_end.astimezone(timezone.utc)
    now=datetime.now(timezone.utc)
    if not (timedelta(0)<end-start<=timedelta(days=31)
            and end<=now and start>=now-timedelta(days=365*5+2)):
        raise ValueError("V418_BOUNDED_WINDOW_REQUIRED")
    if type(dedicated_cash_dsn) is not str or not 1<=len(dedicated_cash_dsn.strip())<=4096:
        raise ValueError("V418_ORIGINAL_OWNER_MANAGED_DSN_REQUIRED")
    try:
        tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V418_ACTIVE_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V418_SIGNED_CRM_TENANT_MISMATCH")
    original=connect_factory is None

    def hold(status:str, numbers: tuple[int,...]|None=None, spent: int|None=None, currencies:int|None=None):
        count,opened,disqualified,dead,converted,linked,unclassified,unlinked = (
            numbers if numbers is not None else (None,)*8
        )
        terminal = disqualified+dead+converted if converted is not None else None
        def percentage(numerator,denominator):
            if denominator is None or denominator==0:
                return None
            return str((Decimal(numerator)*100/Decimal(denominator)).quantize(
                Decimal(".01"),rounding=ROUND_HALF_UP))
        return {
            "schema_version":SCHEMA,"mode":"OBSERVE","status":status,
            "tenant_id":tenant,"start_inclusive":start.isoformat(),
            "end_exclusive":end.isoformat(),
            "original_psycopg_connector":original,
            "database_endpoint_independently_attested":False,
            "custody_claimed_opportunity_count":count,
            "open_count":opened,"disqualified_count":disqualified,
            "dead_count":dead,"converted_claim_count":converted,
            "converted_with_buyer_owned_order_count":linked,
            "missing_state_count":unclassified,
            "converted_but_order_missing_count":unlinked,
            "currency_code":research_twin["currency_code"],
            "mixed_currency_count":currencies,
            "sum_claimed_acquisition_cost_minor":spent,
            "research_cvr_all_opportunities_pct":(
                percentage(linked,count) if count is not None else None
            ),
            "research_cvr_closed_opportunities_pct":(
                percentage(linked,terminal) if terminal is not None else None
            ),
            "research_ecac_minor_per_buyer_order":(
                str((Decimal(spent)/Decimal(linked)).quantize(
                    Decimal("1"),rounding=ROUND_HALF_UP))
                if spent is not None and linked and currencies==1 else None
            ),
            "cvrs_and_ecac_are_unverified_research_only":True,
            "terminal_state_claims_not_independently_verified":True,
            "tenant_custody_population_complete_verified":False,
            "source_rights_independently_verified":False,
            "cash_and_refund_finality_verified":False,
            "actual_net_margin_minor":None,
            "maturation_factors_are_illustrative_only":("0.45","0.80","1.00"),
            "verified_30_60_90_cash_forecasts":None,
            "paid_traffic_budget_minor":0,
            "forecast_calibration_authorized":False,
            "economic_memory_write_authorized":False,
            "outbound_authorized":False,
            "funds_movement_authorized":False,
            "execution_authority":"none",
        }

    if original:
        try:
            import psycopg
            connect_factory=psycopg.connect
        except ImportError:
            return hold("V418_RESTRICTED_CUSTODY_READER_UNAVAILABLE_HELD")
    try:
        with connect_factory(dedicated_cash_dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                cur.execute("SET LOCAL ROLE "+CAPABILITY_ROLE)
                cur.execute("SELECT session_user,current_user")
                if cur.fetchone()!=(READER_LOGIN,CAPABILITY_ROLE):
                    return hold("V418_RESTRICTED_SESSION_IDENTITY_INVALID_HELD")
                cur.execute(SQL,(tenant,start,end))
                rows=cur.fetchall()
        if type(rows) is not list or len(rows)!=1 or type(rows[0]) not in (tuple,list) or len(rows[0])!=15:
            return hold("V418_CUSTODY_COHORT_RESULT_MISSING_HELD")
        r=rows[0]
        counts=r[:8]
        value, currencies, actual_currency=r[8:11]
        if (any(type(x) is not int or not 0<=x<=5000 for x in counts)
            or type(value) not in (int,Decimal) or not 0<=value<=500000000000000
            or value!=int(value)
            or type(currencies) is not int or currencies not in (0,1)
            or counts[1]+counts[2]+counts[3]+counts[4]+counts[6]!=counts[0]
            or counts[5]+counts[7]!=counts[4]
            or counts[5]>counts[4]
            or (counts[0]==0)!=(currencies==0)
            or (actual_currency is not None and actual_currency!=research_twin["currency_code"])
            or (actual_currency is None and counts[0]>0)
            or any(flag is not False for flag in r[11:])):
            return hold("V418_UNTRUSTED_OR_PROMOTED_CUSTODY_RESULT_HELD")
        if not original:
            return hold("V418_INJECTED_CONNECTOR_NOT_INDEPENDENT_EVIDENCE_HELD")
        return hold("V418_BOUNDED_TENANT_CUSTODY_COHORT_ONLY_HELD",
                    tuple(counts),int(value),currencies)
    except Exception:
        return hold("V418_RESTRICTED_CUSTODY_READER_UNAVAILABLE_HELD")
