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
    print(json.dumps({
        "status":"V415_EPHEMERAL_DIRECT_USDT_READ_PASS",
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
