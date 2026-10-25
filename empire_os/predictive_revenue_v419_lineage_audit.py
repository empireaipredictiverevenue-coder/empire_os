"""V4.19 HELD tenant GTM source-lineage audit, same-snapshot V4.18 comparison."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v415_direct_cash_reader import READER_LOGIN, CAPABILITY_ROLE
from empire_os.predictive_revenue_v418_opportunities import SQL as V418_SQL
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v419.source_lineage_held.v1"
SQL = (
 "SELECT selected_custody_claim_count,original_gtm_rows_matched,"
 "empty_source_channel_count,empty_niche_count,empty_opportunity_type_count,"
 "late_custody_claim_over_24h_count,zero_cost_claim_count,"
 "distinct_source_evidence_digests,distinct_owner_evidence_digests,"
 "original_niche_categories,original_source_channel_categories,"
 "original_type_categories,complete_upstream_event_intake_verified,"
 "tenant_owner_provenance_independently_verified,"
 "independent_source_licence_verified,acquisition_cost_invoice_verified,"
 "automated_opportunity_ingestion_authorized "
 "FROM public.read_predictive_revenue_source_lineage_held_v1("
 "%s::uuid,%s::timestamptz,%s::timestamptz)"
)
COUNTERS = (
 "custody_claimed", "original_gtm_matches", "missing_source_channel",
 "missing_niche", "missing_opportunity_type", "late_custody_over_24h",
 "claimed_zero_cost", "distinct_source_digests", "distinct_owner_digests",
 "distinct_niches", "distinct_source_channels", "distinct_opportunity_types",
)

def review_v419_source_lineage_held(
    *, research_twin: dict[str, Any], signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    window_start: datetime, window_end: datetime,
    dedicated_cash_dsn: str,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V419_ORIGINAL_RESEARCH_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V419_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1<=len(signed_crm_bearer)<=4096:
        raise ValueError("V419_SIGNED_BEARER_REQUIRED")
    if type(window_start) is not datetime or type(window_end) is not datetime:
        raise ValueError("V419_TZ_AWARE_WINDOW_REQUIRED")
    if window_start.utcoffset() is None or window_end.utcoffset() is None:
        raise ValueError("V419_TZ_AWARE_WINDOW_REQUIRED")
    start=window_start.astimezone(timezone.utc)
    end=window_end.astimezone(timezone.utc)
    now=datetime.now(timezone.utc)
    if not (timedelta(0)<end-start<=timedelta(days=31) and end<=now
            and start>=now-timedelta(days=365*5+2)):
        raise ValueError("V419_BOUNDED_WINDOW_REQUIRED")
    if type(dedicated_cash_dsn) is not str or not 1<=len(dedicated_cash_dsn.strip())<=4096:
        raise ValueError("V419_DEDICATED_READER_DSN_REQUIRED")
    try:
        tenant=crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V419_ACTIVE_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant!=research_twin["canonical_tenant_id"]:
        raise ValueError("V419_TENANT_BOUNDARY_MISMATCH")
    original=connect_factory is None

    def held(status: str, counters: tuple[int, ...] | None = None,
             missing_states: int | None = None) -> dict[str, Any]:
        counts=counters if counters is not None else (None,)*12
        return {
            "schema_version":SCHEMA,"mode":"OBSERVE","status":status,
            "canonical_tenant_id":tenant,
            "window_start_utc":start.isoformat(),"window_end_utc":end.isoformat(),
            "original_postgresql_connector_used":original,
            "database_endpoint_independently_attested":False,
            "snapshot_isolation":"REPEATABLE_READ",
            **dict(zip(COUNTERS,counts)),
            "missing_state_count":missing_states,
            "source_digest_reuse_is_not_duplicate_proof":True,
            "zero_cost_can_be_legitimate_organic":True,
            "four_sector_taxonomy_verified":False,
            "upstream_opportunity_intake_complete":False,
            "source_rights_independently_verified":False,
            "tenant_owner_provenance_verified":False,
            "acquisition_cost_invoices_verified":False,
            "customer_cvr_verified":False,
            "customer_ecac_verified":False,
            "cash_revenue_verified_minor":None,
            "source_ingestion_authorized":False,
            "paid_traffic_authorized":False,
            "buyer_outreach_authorized":False,
            "economic_memory_write_authorized":False,
            "funds_movement_authorized":False,
            "execution_authority":"none",
        }
    if original:
        try:
            import psycopg
            connect_factory=psycopg.connect
        except ImportError:
            return held("V419_READER_UNAVAILABLE_HELD")

    try:
        with connect_factory(dedicated_cash_dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                cur.execute("SET LOCAL ROLE "+CAPABILITY_ROLE)
                cur.execute("SELECT session_user,current_user")
                if cur.fetchone()!=(READER_LOGIN,CAPABILITY_ROLE):
                    return held("V419_READER_IDENTITY_INVALID_HELD")
                args=(tenant,start,end)
                cur.execute(V418_SQL,args)
                old_rows=cur.fetchall()
                cur.execute(SQL,args)
                lineage_rows=cur.fetchall()
        if (type(old_rows) is not list or len(old_rows)!=1
            or type(old_rows[0]) not in (tuple,list) or len(old_rows[0])!=15
            or type(lineage_rows) is not list or len(lineage_rows)!=1
            or type(lineage_rows[0]) not in (tuple,list)
            or len(lineage_rows[0])!=17):
            return held("V419_INCOMPLETE_COHORT_COMPARISON_HELD")
        old=old_rows[0]
        new=lineage_rows[0]
        counts=new[:12]
        if (any(type(x) is not int or not 0<=x<=5000 for x in old[:8])
            or sum(old[i] for i in (1,2,3,4,6))!=old[0]
            or old[5]+old[7]!=old[4]
            or type(old[8]) not in (int,Decimal)
            or not 0<=old[8]<=500000000000000
            or type(old[9]) is not int or old[9] not in (0,1)
            or (old[0]==0)!=(old[9]==0)
            or old[10]!=(research_twin["currency_code"] if old[0] else None)
            or any(v is not False for v in old[11:])):
            return held("V419_V418_COMPARISON_NOT_TRUSTED_HELD")
        if (any(type(x) is not int or not 0<=x<=5000 for x in counts)
            or any(x is not False for x in new[12:])
            or counts[0]!=old[0] or counts[1]!=old[0]
            or any(x>counts[0] for x in counts[2:])
            or (counts[0]==0 and any(counts[2:]))
            or (counts[0]>0 and (counts[7]==0 or counts[8]==0))):
            return held("V419_UNTRUSTED_SOURCE_METADATA_HELD")
        if not original:
            return held("V419_INJECTED_CONNECTOR_NOT_EVIDENCE_HELD")
        return held("V419_ORIGINAL_GTM_METADATA_AUDITED_HELD",
                    tuple(counts),old[6])
    except Exception:
        return held("V419_READER_UNAVAILABLE_HELD")
