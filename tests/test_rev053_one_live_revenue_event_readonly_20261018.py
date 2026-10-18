"""Rev053: first existing event only, fail closed and no financial claims."""
from __future__ import annotations
from datetime import datetime,timezone
import json
from uuid import UUID
from scripts import review_rev053_one_live_revenue_event_readonly_20261018 as rev

EVENT="abc12345-1234-4234-8234-123412341234"
NOW=datetime(2026,10,18,20,0,0,tzinfo=timezone.utc)
CATALOG_KEYS=(
    "correct_db","login_exists","login_no_admin_noinherit",
    "credential_is_scram","capability_is_nologin",
    "exact_set_only_grant","no_other_granted_memberships",
    "tenant_binding_exactly_one","tenant_binding_no_extra_rows",
    "function_exists","capability_function_execute",
    "login_no_commercial_select","login_no_orders_select",
    "login_no_buyers_select","hba_specific_scram_rule_configured",
    "hba_no_parse_errors"
)
def admin(sql:str,*,event=EVENT,failed_key=None):
    if sql==rev.CATALOG_SQL:
        values={k:(k!=failed_key) for k in CATALOG_KEYS}
        return json.dumps(values)
    if sql==rev.DISCOVER_SQL:
        return event
    raise AssertionError("unreviewed SQL")
def positive_reader(**kwargs):
    assert kwargs["event_id"]==EVENT
    assert kwargs["tenant_id"]==rev.TENANT
    assert "password=" in kwargs["dsn"]
    assert "fixture-password" in kwargs["dsn"]
    return {
        "schema_version":"empire.predictive_revenue.verified_event_read.v1",
        "status":"SINGLE_REVENUE_EVENT_VERIFIED",
        "canonical_event_ref":"canonical:commercial_events:"+EVENT,
        "occurred_at":"2026-10-18T12:34:56+00:00",
        "amount_cents":56789,
        "order_bound":True,"tenant_lineage_matched":True,
        "product_and_price_matched":True,
        "single_event_not_daily_aggregate":True,
        "daily_revenue_census_verified":False,
        "forecast_source_verified":False,
        "revenue_recognition_performed":False,
        "execution_authority":"none"
    }


def test_exact_query_bounded_readonly_single_tenant_candidate():
    sql=rev.DISCOVER_SQL
    assert sql.startswith("BEGIN READ ONLY;")
    assert sql.rstrip().endswith("ROLLBACK;")
    assert "LIMIT 1" in sql
    assert "statement_timeout='5000ms'" in sql
    assert "event_buyer.org_id='"+rev.TENANT+"'::uuid" in sql
    assert "order_buyer.org_id='"+rev.TENANT+"'::uuid" in sql
    assert "e.event_type='revenue_recognized'" in sql
    assert "e.payload->>'actual_revenue'='true'" in sql
    assert "o.state IN ('settled','outcome_captured')" in sql
    assert "e.amount_cents=o.price_cents" in sql
    assert "e.payload->'causal_lineage'" in sql
    assert "current_setting('archive" not in sql
    assert "SELECT e.id::text" in sql
    assert "SELECT *" not in sql
    assert "INSERT INTO" not in sql
    assert "UPDATE " not in sql
    assert "DELETE " not in sql


def test_catalog_hold_prevents_candidate_and_password_read():
    def fail_read():
        raise AssertionError("credential must not be opened")
    result=rev.execute_review(admin_query=lambda sql:admin(sql,failed_key="login_no_commercial_select"),
                              private_key=fail_read,now=NOW)
    assert result["stage"]=="AUTHORITY_CATALOG_HOLD"
    assert result["status"].startswith("HOLD_")
    assert result["database_writes"] is False


def test_no_real_candidate_is_not_misrepresented_as_zero_revenue():
    result=rev.execute_review(
        admin_query=lambda sql:admin(sql,event=rev.MISSING),
        private_key=lambda:(_ for _ in ()).throw(AssertionError("no password needed")),
        now=NOW
    )
    assert result["status"]=="REV053_NO_ELIGIBLE_EXISTING_EVENT_FOUND"
    assert result["one_candidate_reviewed"] is False
    assert result["realised_revenue_verified"] is False
    assert "amount_minor_units" not in result


def test_mismatched_id_not_accepted():
    result=rev.execute_review(
        admin_query=lambda sql:admin(sql,event="something-untrusted"),
        private_key=lambda:(_ for _ in ()).throw(AssertionError("no password")),
        now=NOW
    )
    assert result["stage"]=="UNEXPECTED_CANDIDATE_SHAPE"


def test_one_matching_canonical_event_limited_claims_and_fingerprint():
    result=rev.execute_review(admin_query=admin,private_key=lambda:"fixture-password",
                              event_reader=positive_reader,now=NOW)
    assert result["status"]=="REV053_ONE_EXISTING_CANONICAL_LEDGER_EVENT_MATCHED"
    assert result["amount_minor_units"]==56789
    assert result["monetary_unit"]=="UNVERIFIED_SOURCE_UNIT_NO_CURRENCY_ASSERTED"
    assert len(result["event_ref_fingerprint"])==16
    assert EVENT not in json.dumps(result)
    assert "fixture-password" not in json.dumps(result)
    assert result["realised_revenue_verified"] is False
    assert result["real_payment_settlement_verified"] is False
    assert result["complete_daily_revenue_census_verified"] is False
    assert result["customer_financial_report_authorized"] is False


def test_fake_attestation_cannot_authorize_claim():
    def fake(**kwargs):
        record=positive_reader(**kwargs)
        record["tenant_lineage_matched"]=False
        return record
    result=rev.execute_review(admin_query=admin,private_key=lambda:"fixture-password",
                              event_reader=fake,now=NOW)
    assert result["stage"]=="CANONICAL_EVENT_ATTESTATION_UNTRUSTED"
    assert "amount_minor_units" not in result


def test_exception_no_sensitive_data_leak():
    def raise_sql(sql):
        raise RuntimeError("password=PRIVATE")
    result=rev.execute_review(admin_query=raise_sql,now=NOW)
    assert "PRIVATE" not in json.dumps(result)
    assert result["stage"]=="AUTHORITY_CATALOG_UNAVAILABLE"


def test_no_root_no_cli_flag(monkeypatch,capsys):
    assert rev.main([])==2
    assert "HOLD_EXPLICIT" in capsys.readouterr().out
    monkeypatch.setattr(rev.os,"geteuid",lambda:1000)
    assert rev.main(["--read-only-one-event"])==2
    assert "HOLD_ROOT_LOCAL_SESSION_REQUIRED" in capsys.readouterr().out
