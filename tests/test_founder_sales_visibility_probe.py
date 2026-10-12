"""No live prospect insertion and no PII disclosure in CRM visibility probe."""
import json
from pathlib import Path

from scripts import probe_founder_sales_visibility_readonly as probe


def test_zero_scope_not_misrepresented_as_no_global_enquiries(tmp_path):
    records=[]
    def query(role,sql,temp):
        records.append((role,sql,temp.stat().st_mode & 0o777))
        return 0,"0|0|0",""
    result=probe.run(read_private=lambda:b"fixture-test-password",
                     query=query,temporary_directory=tmp_path)
    assert result["status"]=="NO_TENANT_VISIBLE_SALES_PROSPECTS"
    assert result["visible_total_prospects"]==0
    assert result["canonical_global_intake_count_proven"] is False
    assert result["website_to_founder_visibility_proven"] is False
    assert records[0][2]==0o600
    assert "BEGIN READ ONLY" in records[0][1]
    assert "SET LOCAL ROLE empire_revenue_crm_reader" in records[0][1]
    assert "public.revenue_crm_prospects" in records[0][1]
    assert "tenant_id=public.empire_current_tenant_id()" in records[0][1]
    assert "INSERT" not in records[0][1]
    assert "UPDATE" not in records[0][1]
    assert list(tmp_path.iterdir())==[]


def test_positive_counts_still_not_prove_single_website_submission(tmp_path):
    result=probe.run(
        read_private=lambda:b"fixture-test-password",
        query=lambda *args:(0,"2|1|7",""),
        temporary_directory=tmp_path)
    assert result["status"]=="TENANT_VISIBLE_SALES_PROSPECTS_PRESENT"
    assert result["visible_commercial_sales_prospects"]==2
    assert result["visible_predictive_revenue_prospects"]==1
    assert result["visible_total_prospects"]==7
    assert result["website_to_founder_visibility_proven"] is False
    assert result["outbound_authorized"] is False


def test_driver_error_cannot_leak_private_credentials_or_sql(tmp_path):
    password="VERY_SECRET_FIXTURE_TOKEN"
    result=probe.run(
        read_private=lambda:password.encode(),
        query=lambda *args:(2,"postgresql://secret@example.invalid",
                            "VERY_SECRET_FIXTURE_TOKEN command error"),
        temporary_directory=tmp_path)
    serialized=json.dumps(result)
    assert result["status"]=="UNVERIFIED"
    assert password not in serialized
    assert "postgresql://" not in serialized
    assert result["payment_authorized"] is False
    assert list(tmp_path.iterdir())==[]


def test_malformed_or_impossible_counts_never_claim_success():
    for value in ("2|1|1","-1|0|0","0|0|","0|foo|3",
                  "password|0|1","0|0|0\n1|1|1"):
        assert probe.parse_aggregate(0,value) is None
    assert probe.parse_aggregate(1,"0|0|0") is None
    assert probe.parse_aggregate(0,"1|1|3")=={
        "visible_commercial_sales_prospects":1,
        "visible_predictive_revenue_prospects":1,
        "visible_total_prospects":3,
    }


def test_missing_passfile_fails_closed_without_query(tmp_path):
    result=probe.run(
        read_private=lambda:(_ for _ in ()).throw(ValueError("a_password")),
        query=lambda *args:(_ for _ in ()).throw(AssertionError("DB must not be queried")),
        temporary_directory=tmp_path)
    assert result["status"]=="UNVERIFIED"
    assert "a_password" not in str(result)
    assert result["tenant_binding_mutated"] is False
    assert result["raw_customer_rows_read"] is False
    assert result["prospect_ingest_performed"] is False
