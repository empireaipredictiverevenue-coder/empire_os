"""V4.20 source-license, event-coverage and settlement CLAIMS; never authority.

Single original EmpireDB, existing dedicated reader and Smart CRM membership.
No production write, no schema activation, no real settlement attestation.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Callable

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v415_direct_cash_reader import CAPABILITY_ROLE, READER_LOGIN
from empire_os.predictive_revenue_v419_lineage_audit import SQL as LINEAGE_SQL
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA="empire.predictive_revenue.v420.three_pillar_audit_held.v1"
SQL=(
 "SELECT opportunity_count,source_document_claim_count,"
 "claimed_active_source_count,event_evidence_claim_count,"
 "matched_source_and_event_claim_count,original_accepted_order_opportunity_count,"
 "paired_clearing_claim_count,conflicting_clearing_claim_count,"
 "claimed_acquisition_cost_minor,claimed_coverage_basis_points,"
 "source_licensing_independently_verified,"
 "upstream_event_census_independently_verified,independent_settlement_verified,"
 "fully_audited_authorized,verified_cvr_ecac_authorized,"
 "verified_30_60_90_cash_authorized "
 "FROM public.read_predictive_revenue_three_pillar_held_v1("
 "%s::uuid,%s::text,%s::timestamptz,%s::timestamptz)"
)
CHANNEL=re.compile(r"^[a-z0-9_]{2,48}$")

def review_v420_three_pillar_held(
    *, research_twin: dict[str,Any], signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier, channel_name: str,
    window_start: datetime,window_end: datetime,
    dedicated_cash_dsn: str,
    connect_factory: Callable | None = None,
) -> dict[str,Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V420_ORIGINAL_RESEARCH_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V420_ORIGINAL_SIGNED_CRM_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V420_SIGNED_BEARER_REQUIRED")
    if type(channel_name) is not str or not CHANNEL.fullmatch(channel_name):
        raise ValueError("V420_EXACT_BOUNDED_CHANNEL_REQUIRED")
    if type(window_start) is not datetime or type(window_end) is not datetime:
        raise ValueError("V420_TZ_AWARE_WINDOW_REQUIRED")
    if window_start.utcoffset() is None or window_end.utcoffset() is None:
        raise ValueError("V420_TZ_AWARE_WINDOW_REQUIRED")
    start,end=window_start.astimezone(timezone.utc),window_end.astimezone(timezone.utc)
    now=datetime.now(timezone.utc)
    if not (timedelta(0)<end-start<=timedelta(days=31)
            and end<=now and start>=now-timedelta(days=365*5+2)):
        raise ValueError("V420_BOUNDED_WINDOW_REQUIRED")
    if type(dedicated_cash_dsn) is not str or not 1<=len(dedicated_cash_dsn.strip())<=4096:
        raise ValueError("V420_DEDICATED_READER_DSN_REQUIRED")
    try:
        tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V420_ACTIVE_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V420_CRM_TWIN_TENANT_MISMATCH")
    original=connect_factory is None

    def held(status: str, values: tuple | None = None) -> dict[str,Any]:
        amounts=values if values is not None else (None,)*10
        (total,licensed_claims,active_claims,raw_claims,paired_source,
         accepted_orders,paired_clearing,conflicts,cost,bps)=amounts
        if values is None or total==0:
            tier="UNVERIFIED"
        elif any((licensed_claims,raw_claims,paired_clearing,conflicts)):
            tier="PARTIAL_COVERAGE"
        else:
            tier="UNVERIFIED"
        return {
            "schema_version":SCHEMA,"mode":"OBSERVE","status":status,
            "canonical_tenant_id":tenant,"channel":channel_name,
            "window_start_utc":start.isoformat(),
            "window_end_utc":end.isoformat(),
            "original_postgresql_connector_used":original,
            "endpoint_independently_attested":False,
            "database_snapshot":"REPEATABLE_READ",
            "opportunities_in_claimed_channel":total,
            "source_authorization_document_claims":licensed_claims,
            "claimed_active_source_count":active_claims,
            "event_payload_or_cdr_claims":raw_claims,
            "source_and_event_claims_paired":paired_source,
            "accepted_order_linked_opportunities":accepted_orders,
            "paired_remittance_clearing_claims":paired_clearing,
            "conflicting_finance_claims":conflicts,
            "claimed_acquisition_cost_minor":cost,
            "claimed_source_event_coverage_bps":bps,
            "research_readiness_tier":tier,
            "fully_audited_independently_verified":False,
            "source_licence_independently_verified":False,
            "upstream_inbound_denominator_verified":False,
            "financial_settlement_independently_verified":False,
            "source_match_claim_not_license":True,
            "paired_hashes_not_independent_cash_proof":True,
            "fully_audited_channel_count":0,
            "verified_cvr_ecac_authorized":False,
            "verified_30_60_90_cash_forecasts":None,
            "economic_memory_write_authorized":False,
            "model_learning_authorized":False,
            "paid_traffic_authorized":False,
            "outbound_authorized":False,
            "funds_movement_authorized":False,
            "execution_authority":"none",
        }
    if original:
        try:
            import psycopg
            connect_factory=psycopg.connect
        except ImportError:
            return held("V420_ORIGINAL_READER_UNAVAILABLE_HELD")

    try:
        with connect_factory(dedicated_cash_dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                cur.execute("SET LOCAL ROLE "+CAPABILITY_ROLE)
                cur.execute("SELECT session_user,current_user")
                if cur.fetchone()!=(READER_LOGIN,CAPABILITY_ROLE):
                    return held("V420_ORIGINAL_READER_IDENTITY_INVALID_HELD")
                cur.execute(LINEAGE_SQL,(tenant,start,end))
                older=cur.fetchall()
                cur.execute(SQL,(tenant,channel_name,start,end))
                newer=cur.fetchall()
        if (type(older) is not list or len(older)!=1
            or type(older[0]) not in (tuple,list) or len(older[0])!=17
            or type(newer) is not list or len(newer)!=1
            or type(newer[0]) not in (tuple,list) or len(newer[0])!=16):
            return held("V420_MISSING_CONSISTENT_EVIDENCE_ROWS_HELD")
        past,latest=older[0],newer[0]
        measures=latest[:8]
        cost,bps=latest[8:10]
        if (any(type(x) is not int or not 0<=x<=5000 for x in past[:12])
            or past[0]!=past[1] or any(x is not False for x in past[12:])):
            return held("V420_ORIGINAL_LINEAGE_EVIDENCE_NOT_TRUSTED_HELD")
        expected_bps=(
            int((Decimal(measures[4])*10000/Decimal(measures[0])).quantize(
                Decimal("1"),rounding=ROUND_HALF_UP))
            if measures[0]>0 else None
        )
        if (any(type(x) is not int or not 0<=x<=5000 for x in measures)
            or any(x>measures[0] for x in measures[1:])
            or measures[0]>past[0] or measures[2]>measures[1]
            or measures[4]>measures[2] or measures[4]>measures[3]
            or measures[6]>measures[5] or measures[7]>measures[5]
            or type(cost) not in (int,Decimal) or cost!=int(cost)
            or not 0<=cost<=500000000000000
            or (bps is not None and type(bps) is not int)
            or bps!=expected_bps
            or any(x is not False for x in latest[10:])):
            return held("V420_UNTRUSTED_OR_PROMOTED_THREE_PILLAR_DATA_HELD")
        if not original:
            return held("V420_INJECTED_CONNECTOR_NOT_SOURCE_PROOF_HELD")
        return held("V420_THREE_PILLAR_CLAIMS_ONLY_HELD",
                    tuple(measures)+(int(cost),bps))
    except Exception:
        return held("V420_ORIGINAL_READER_UNAVAILABLE_HELD")
