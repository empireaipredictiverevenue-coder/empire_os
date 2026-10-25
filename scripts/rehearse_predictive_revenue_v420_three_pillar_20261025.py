#!/usr/bin/env python3
"""V4.15 actual held SQL via disposable PG18, no production side effects."""
from __future__ import annotations

import json
import os
import subprocess
import base64

import psycopg
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_revenue_v415_direct_cash_reader import (
    review_v415_cash_candidates_held,
)
from empire_os.predictive_revenue_v416_operational_reversals import (
    review_v416_reversal_signals_held,
)
from empire_os.predictive_revenue_v417_order_cohort import review_v417_tenant_order_cohort_held
from empire_os.predictive_revenue_v418_opportunities import review_v418_opportunity_custody_held
from empire_os.predictive_revenue_v419_lineage_audit import review_v419_source_lineage_held
from empire_os.predictive_revenue_v420_three_pillar_audit import review_v420_three_pillar_held
from datetime import datetime,timezone,timedelta

DB="empire_v415_fixture"
LOGIN="empire_predictive_cash_candidate_login"
CAPABILITY="empire_predictive_cash_candidate_reader"
TENANT="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DIRECT="33333333-3333-4333-8333-333333333333"
FOREIGN="44444444-4444-4444-8444-444444444444"
ESCROW="55555555-5555-4555-8555-555555555555"
TOO_FEW_CONFIRMATIONS="66666666-6666-4666-8666-666666666666"

def must_be_ephemeral():
    if os.environ.get("PGHOST") != "localhost":
        raise ValueError("V415_NON_EPHEMERAL_HOST_REJECTED")
    try:port=int(os.environ["PGPORT"])
    except (ValueError,KeyError):raise ValueError("V415_NON_EPHEMERAL_PORT_REJECTED") from None
    if port <= 5432:raise ValueError("V415_PRODUCTION_PORT_REJECTED")
    result=subprocess.run([
        "psql","-XAtq","-v","ON_ERROR_STOP=1","-d","postgres","-c","SHOW data_directory"
    ],capture_output=True,text=True,check=True,timeout=8).stdout.strip()
    if not result.startswith("/tmp/pg_virtualenv.") or not result.endswith("/data/18/regress"):
        raise ValueError("V415_NOT_DISPOSABLE_PG18")
    return port

def query(cur, tenant, orders):
    cur.execute(
        "SELECT selected_order_id::text,evidence_status,"
        "selected_direct_usdt_candidate_usd_cents,"
        "payment_and_tenant_lineage_matches,"
        "independent_refund_finality_verified,"
        "cash_collected_by_finance_verified,commercial_action_authorized "
        "FROM public.read_predictive_direct_bsc_cash_candidate_v1(%s::uuid,%s::uuid[])",
        (tenant, orders))
    return cur.fetchall()

def main():
    port=must_be_ephemeral()
    dsn=(f"host=127.0.0.1 port={port} dbname={DB} user={LOGIN} "
         f"password={os.environ['V415_EPHEMERAL_PASSWORD']}")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            cur.execute("SELECT session_user,current_user")
            assert cur.fetchone() == (LOGIN,CAPABILITY)
            data=query(cur,TENANT,[DIRECT,FOREIGN,ESCROW,TOO_FEW_CONFIRMATIONS])
            assert len(data)==4
            by_id={x[0]:x for x in data}
            assert len(by_id)==4
            yes=by_id[DIRECT]
            assert yes[1]=="DIRECT_USDT_BSC_TRANSFER_CANDIDATE_HELD"
            assert yes[2]==25000 and yes[3] is True
            assert yes[4:] == (False,False,False)
            for key in [FOREIGN,ESCROW,TOO_FEW_CONFIRMATIONS]:
                row=by_id[key]
                assert row[1]=="NO_UNAMBIGUOUS_DIRECT_BSC_EVIDENCE_HELD"
                assert row[2] is None and row[3] is False
                assert row[4:]==(False,False,False)
    # A missing active session-bound tenant or duplicate selection MUST error.
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:query(cur,OTHER,[DIRECT])
            except psycopg.errors.RaiseException as exc:
                assert "V415_SESSION_BOUND_TENANT_REQUIRED" in str(exc)
            else:raise AssertionError("CROSS_TENANT_SELECTED_DATA_RETURNED")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:query(cur,TENANT,[DIRECT,DIRECT])
            except psycopg.errors.RaiseException as exc:
                assert "V415_BOUNDED_UNIQUE_EXPLICIT_ORDER_SET_REQUIRED" in str(exc)
            else:raise AssertionError("DUPLICATE_ORDER_READ_ALLOWED")
    # No SELECT on parent tables, even under explicit SET ROLE.
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute("SELECT * FROM public.bsc_payment_evidence LIMIT 1")
            except psycopg.errors.InsufficientPrivilege:pass
            else:raise AssertionError("DIRECT_TABLE_SELECT_GRANTED")
    # Original signed CRM active-member verifier + original bounded reader
    # against the actual disposable SQL and SCRAM-protected login.
    key=Ed25519PrivateKey.generate()
    at=1800000000
    verifier=SignedCrmTenantVerifier(
        {"v415-fixture":key.public_key()},
        load_membership=lambda sub,tenant:TenantMembership(
            tenant_id=TENANT,user_id=sub,role="owner",status="active",
        ),now=lambda:at,
    )
    enc=lambda obj:base64.urlsafe_b64encode(
        json.dumps(obj,sort_keys=True).encode()).rstrip(b"=").decode()
    header=enc({"alg":"EdDSA","kid":"v415-fixture","typ":"JWT"})
    claim=enc({
        "iss":"empire-os","aud":"empire-revenue-crm","sub":"founder-1",
        "tenant_id":TENANT,"scope":"crm:read",
        "iat":at-2,"nbf":at-2,"exp":at+120,
        "jti":"v415-pg18-actual-cash-reader-0001",
    })
    unsigned=header+"."+claim
    jwt=unsigned+"."+base64.urlsafe_b64encode(
        key.sign(unsigned.encode())).rstrip(b"=").decode()
    held_twin={
        "schema_version":"empire.predictive_revenue.v412.synthetic_cash_twin.v1",
        "mode":"SIMULATION","simulation_only":True,
        "execution_authority":"none","licensed_source_admitted":False,
        "forecast_empirically_calibrated":False,
        "approved_commercial_forecast":False,
        "revenue_recognised_cents":None,
        "currency_code":"USD","canonical_tenant_id":TENANT,
        "source_evidence_digest":"a"*64,
        "forecast_horizons":{
            str(x):{"p10_gross_cash_cents":0,"p50_gross_cash_cents":0,
                    "p90_gross_cash_cents":0} for x in (30,60,90)
        },
    }
    joined=review_v415_cash_candidates_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,
        exact_order_ids=(DIRECT,FOREIGN,ESCROW,TOO_FEW_CONFIRMATIONS),
        dedicated_cash_dsn=dsn,
    )
    assert joined["status"]=="V415_SCOPED_DIRECT_TRANSFER_CANDIDATES_ONLY_HELD",joined
    assert joined["original_postgresql_connector_used"] is True
    assert joined["database_endpoint_independently_attested"] is False
    assert joined["direct_transfer_candidate_count"]==1
    assert joined["unknown_or_unverified_order_count"]==3
    assert joined["claim_not_collected_cash"] is True
    assert joined["actual_cash_collected_minor_units"] is None
    assert joined["funds_movement_authorized"] is False
    # V4.16 prepared 068: read original tenant's operational reversal
    # SIGNALS, never financial refund or verified collected cash.
    signal=review_v416_reversal_signals_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,
        exact_order_ids=(DIRECT,FOREIGN,ESCROW,TOO_FEW_CONFIRMATIONS),
        dedicated_cash_dsn=dsn,
    )
    assert signal["status"]=="V416_BOUNDED_OPERATIONAL_REVERSAL_OBSERVATIONS_HELD", signal
    assert signal["orders_with_refund_like_delivery_signal"] == 1,signal
    assert signal["orders_with_failure_or_rejection_delivery_signal"] == 1,signal
    assert signal["orders_with_unknown_visibility"] == 1,signal
    assert signal["net_cash_earned_minor_units"] is None
    assert signal["full_reversal_event_census_verified"] is False
    assert signal["execution_authority"] == "none"
    # Exact session identity, cross-tenant and duplicate refusal on 068 too.
    query_sql=(
        "SELECT selected_order_id::text,operational_signal_status,"
        "refunded_delivery_signal_count,failed_or_rejected_delivery_signal_count,"
        "monetary_reversal_independently_verified,full_refund_census_verified,"
        "net_cash_earned_verified,automatic_execution_authorized "
        "FROM public.read_predictive_revenue_reversal_signals_v1(%s::uuid,%s::uuid[])"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            cur.execute(query_sql,(TENANT,[DIRECT,FOREIGN,ESCROW,TOO_FEW_CONFIRMATIONS]))
            rows=cur.fetchall()
            assert len(rows)==4
            byid={r[0]:r for r in rows}
            assert byid[DIRECT][1:4]==("REFUND_LIKE_DELIVERY_SIGNAL_HELD",1,0)
            assert byid[FOREIGN][1:4]==("ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD",0,0)
            assert byid[ESCROW][1:4]==("FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD",0,1)
            assert byid[TOO_FEW_CONFIRMATIONS][1:4]==("NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD",0,0)
            assert all(row[4:] == (False,False,False,False) for row in rows)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(query_sql,(OTHER,[DIRECT]))
            except psycopg.errors.RaiseException as e:
                assert "V416_SESSION_TENANT_DENIED" in str(e)
            else:raise AssertionError("V416_CROSS_TENANT_ALLOWED")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(query_sql,(TENANT,[DIRECT,DIRECT]))
            except psycopg.errors.RaiseException as e:
                assert "V416_BOUNDED_UNIQUE_ORDERS_REQUIRED" in str(e)
            else:raise AssertionError("V416_DUPLICATE_ALLOWED")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute("SELECT id FROM public.commercial_outcomes LIMIT 1")
            except psycopg.errors.InsufficientPrivilege:pass
            else:raise AssertionError("V416_RAW_OUTCOME_TABLE_SELECT_ALLOWED")
    # Complete buyer-owned order cohort for the original tenant in [start,end).
    now=datetime.now(timezone.utc)
    begin=now-timedelta(days=14)
    end=now-timedelta(days=1)
    census=review_v417_tenant_order_cohort_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,window_start=begin,window_end=end,
        dedicated_cash_dsn=dsn,
    )
    assert census["status"]=="V417_BOUNDED_TENANT_ORDER_COHORT_ONLY_HELD",census
    assert census["buyer_owned_order_count"]==7,census
    assert census["orders_currently_settled_or_outcome_captured"]==4,census
    assert census["orders_currently_rejected"]==1,census
    assert census["orders_currently_cancelled"]==1,census
    assert census["orders_currently_other_or_open"]==1,census
    assert census["orders_without_opportunity_link"]==1,census
    assert census["distinct_linked_opportunities_in_orders"]==5,census
    assert census["order_cohort_window_complete_under_buyer_ownership"] is True
    assert census["gtm_opportunity_denominator_complete"] is False
    assert census["eligible_for_revenue_forecast_calibration"] is False
    assert census["actual_cash_collected_minor_units"] is None
    query_sql=(
        "SELECT selected_order_count,current_state_settled_or_outcome_captured,"
        "current_state_rejected,current_state_cancelled,current_state_other_or_open,"
        "selected_orders_without_opportunity_id,distinct_order_linked_opportunity_ids,"
        "multiple_orders_per_opportunity,complete_buyer_owned_order_window_scanned,"
        "complete_gtm_opportunity_denominator_verified,"
        "historical_status_as_of_window_end_verified,"
        "settled_cash_independently_verified,eligible_for_revenue_model_calibration "
        "FROM public.read_predictive_revenue_tenant_order_cohort_v1("
        "%s::uuid,%s::timestamptz,%s::timestamptz)"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            cur.execute(query_sql,(TENANT,begin,end))
            rows=cur.fetchall()
            assert len(rows)==1 and rows[0]==(
                7,4,1,1,1,1,5,True,True,False,False,False,False),rows
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(query_sql,(OTHER,begin,end))
            except psycopg.errors.RaiseException as e:
                assert "V417_SESSION_BOUND_TENANT_REQUIRED" in str(e)
            else:raise AssertionError("V417_CROSS_TENANT_ALLOWED")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(query_sql,(TENANT,begin-timedelta(days=100),end))
            except psycopg.errors.RaiseException as e:
                assert "V417_BOUNDED_HISTORICAL_WINDOW_REQUIRED" in str(e)
            else:raise AssertionError("V417_UNBOUNDED_COHORT_ALLOWED")
    claimed=review_v418_opportunity_custody_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,window_start=begin,window_end=end,
        dedicated_cash_dsn=dsn,
    )
    assert claimed["status"]=="V418_BOUNDED_TENANT_CUSTODY_COHORT_ONLY_HELD",claimed
    assert claimed["custody_claimed_opportunity_count"]==7,claimed
    assert claimed["open_count"]==2,claimed
    assert claimed["disqualified_count"]==1,claimed
    assert claimed["dead_count"]==1,claimed
    assert claimed["converted_claim_count"]==2,claimed
    assert claimed["converted_with_buyer_owned_order_count"]==2,claimed
    assert claimed["missing_state_count"]==1,claimed
    assert claimed["converted_but_order_missing_count"]==0,claimed
    assert claimed["sum_claimed_acquisition_cost_minor"]==700,claimed
    assert claimed["research_cvr_all_opportunities_pct"]=="28.57",claimed
    assert claimed["research_cvr_closed_opportunities_pct"]=="50.00",claimed
    assert claimed["research_ecac_minor_per_buyer_order"]=="350",claimed
    assert claimed["tenant_custody_population_complete_verified"] is False
    assert claimed["actual_net_margin_minor"] is None
    assert claimed["verified_30_60_90_cash_forecasts"] is None
    assert claimed["paid_traffic_budget_minor"]==0
    assert claimed["execution_authority"]=="none"
    # Table ACL: restricted reader cannot enumerate either ledger.
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute("SELECT opportunity_id FROM public.empire_predictive_opportunity_custody_v418 LIMIT 1")
            except psycopg.errors.InsufficientPrivilege:pass
            else:raise AssertionError("V418_UNSCOPED_TABLE_READ")
    # Actual SQL tenant replay denial.
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(
                "SELECT * FROM public.read_predictive_revenue_gtm_denominator_v418(%s,%s,%s)",
                (OTHER,begin,end))
            except psycopg.errors.RaiseException as exc:
                assert "V418_SESSION_TENANT_REQUIRED" in str(exc)
            else:raise AssertionError("V418_CROSS_TENANT_COHORT_READ")
    lineage=review_v419_source_lineage_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,window_start=begin,window_end=end,
        dedicated_cash_dsn=dsn,
    )
    assert lineage["status"]=="V419_ORIGINAL_GTM_METADATA_AUDITED_HELD",lineage
    assert lineage["custody_claimed"]==7,lineage
    assert lineage["original_gtm_matches"]==7,lineage
    assert lineage["missing_source_channel"]==1,lineage
    assert lineage["missing_niche"]==1,lineage
    assert lineage["missing_opportunity_type"]==1,lineage
    assert lineage["late_custody_over_24h"]==1,lineage
    assert lineage["claimed_zero_cost"]==0,lineage
    assert lineage["distinct_source_digests"]==1,lineage
    assert lineage["distinct_owner_digests"]==1,lineage
    assert lineage["missing_state_count"]==1,lineage
    assert lineage["upstream_opportunity_intake_complete"] is False
    assert lineage["source_rights_independently_verified"] is False
    assert lineage["customer_cvr_verified"] is False
    assert lineage["cash_revenue_verified_minor"] is None
    assert lineage["execution_authority"]=="none"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute("SELECT id FROM public.gtm_opportunities LIMIT 1")
            except psycopg.errors.InsufficientPrivilege:pass
            else:raise AssertionError("V419_GTM_RAW_SELECT_ALLOWED")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(
                "SELECT * FROM public.read_predictive_revenue_source_lineage_held_v1(%s,%s,%s)",
                (OTHER,begin,end))
            except psycopg.errors.RaiseException as exc:
                assert "V419_SESSION_TENANT_DENIED" in str(exc)
            else:raise AssertionError("V419_OTHER_TENANT_LEAK")
    audit=review_v420_three_pillar_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,channel_name="organic",
        window_start=begin,window_end=end,dedicated_cash_dsn=dsn,
    )
    assert audit["status"]=="V420_THREE_PILLAR_CLAIMS_ONLY_HELD",audit
    assert audit["opportunities_in_claimed_channel"]==6,audit
    assert audit["source_authorization_document_claims"]==6,audit
    assert audit["claimed_active_source_count"]==6,audit
    assert audit["event_payload_or_cdr_claims"]==3,audit
    assert audit["source_and_event_claims_paired"]==3,audit
    assert audit["accepted_order_linked_opportunities"]==3,audit
    assert audit["paired_remittance_clearing_claims"]==1,audit
    assert audit["conflicting_finance_claims"]==1,audit
    assert audit["claimed_acquisition_cost_minor"]==600,audit
    assert audit["claimed_source_event_coverage_bps"]==5000,audit
    assert audit["research_readiness_tier"]=="PARTIAL_COVERAGE",audit
    assert audit["fully_audited_independently_verified"] is False
    assert audit["verified_cvr_ecac_authorized"] is False
    assert audit["verified_30_60_90_cash_forecasts"] is None
    assert audit["funds_movement_authorized"] is False
    assert audit["execution_authority"]=="none"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute("SELECT * FROM public.empire_predictive_financial_match_claims_v420 LIMIT 1")
            except psycopg.errors.InsufficientPrivilege:pass
            else:raise AssertionError("V420_RAW_FINANCE_TABLE_EXPOSED")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE "+CAPABILITY)
            try:cur.execute(
              "SELECT * FROM public.read_predictive_revenue_three_pillar_held_v1(%s,%s,%s,%s)",
              (OTHER,"organic",begin,end))
            except psycopg.errors.RaiseException as ex:
                assert "V420_SIGNED_SESSION_TENANT_REQUIRED" in str(ex)
            else:raise AssertionError("V420_TENANT_CROSS_READ")
    # Revocation is append-only, so a previous CLAIMED_ACTIVE document loses
    # its positive claimed coverage. Still never sufficient for source admission.
    subprocess.run([
        "psql","-Xq","-v","ON_ERROR_STOP=1","-d",DB,"-c",
        "SET ROLE empiredb_migrator; INSERT INTO public.empire_predictive_source_revocation_claims_v420 "
        "(tenant_id,source_evidence_digest,channel_name,revocation_evidence_digest,claimed_revoked_at) "
        "VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',repeat('a',64),'organic',repeat('f',64),now());"
    ],check=True,capture_output=True,text=True,timeout=10)
    revoked=review_v420_three_pillar_held(
        research_twin=held_twin,signed_crm_bearer=jwt,
        crm_verifier=verifier,channel_name="organic",
        window_start=begin,window_end=end,dedicated_cash_dsn=dsn,
    )
    assert revoked["status"]=="V420_THREE_PILLAR_CLAIMS_ONLY_HELD",revoked
    assert revoked["claimed_active_source_count"]==0,revoked
    assert revoked["source_and_event_claims_paired"]==0,revoked
    assert revoked["claimed_source_event_coverage_bps"]==0,revoked
    assert revoked["research_readiness_tier"]=="PARTIAL_COVERAGE"
    assert revoked["fully_audited_independently_verified"] is False
    print(json.dumps({
        "status":"V420_EPHEMERAL_THREE_PILLAR_PASS",
        "pg18_isolated":True,
        "dedicated_login_and_set_only_reader":True,
        "one_valid_direct_transfer_candidate":True,
        "cross_tenant_unknown":True,
        "escrow_not_inferred":True,
        "low_confirmation_not_inferred":True,
        "duplicate_selection_denied":True,
        "direct_table_select_denied":True,
        "candidate_is_final_cash":False,
        "cash_refund_finality_verified":False,
        "production_db_writes":False,
        "live_payments_enabled":False,
    },sort_keys=True))

if __name__=="__main__":
    main()
