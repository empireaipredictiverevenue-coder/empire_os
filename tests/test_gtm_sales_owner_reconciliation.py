from datetime import datetime, timedelta, timezone
import json

from empire_os.gtm_sales_owner_reconciliation import (
    SCHEMA, OWNER_SCHEMA, RECEIPT, public_review, observe_owner_sales,
)
from scripts import publish_gtm_sales_owner_reconciliation as owner

NOW=datetime(2026,10,23,10,0,tzinfo=timezone.utc)


def packet(n=1):
    return {
        "schema_version":SCHEMA,
        "source_schema_version":OWNER_SCHEMA,
        "source_status":("NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH"
                         if n else "NO_CANONICAL_SALES_ACQUISITION_OBSERVED"),
        "generated_at_utc":NOW.isoformat(),
        "read_only":True, "execution_authority":"none",
        "commercial_acquisition_rows":n,"predictive_acquisition_rows":0,
        "sales_acquisition_rows":n,"distinct_sales_prospects":n,
        "source_evidence_consistent_rows":n,
        "entity_unlinked_acquisition_rows":0,
        "founder_binding_exact_one_rows":n,
        "founder_binding_missing_or_ambiguous_rows":0,
        "visible_commercial_sales_prospects":n,
        "visible_predictive_revenue_prospects":0,
        "visible_total_prospects":n,
    }


def test_nonzero_counts_still_do_not_prove_an_exact_customer():
    result=public_review(packet(),now=NOW)
    assert result["source_and_tenant_aggregate_valid"] is True
    assert result["canonical_sales_acquisitions"] == 1
    assert result["status"]=="SOURCE_OR_CRM_EVIDENCE_NEEDS_FOUNDER_REVIEW"
    for k in ("exact_enquiry_lineage_verified",
              "contact_consent_for_this_enquiry_verified",
              "founder_crm_delivery_verified","outreach_authorized",
              "payments_authorized","crm_write_authorized"):
        assert result[k] is False
    assert "@" not in json.dumps(result)


def test_owner_verified_zero_is_not_misreported_as_unknown():
    result=public_review(packet(0),now=NOW)
    assert result["canonical_sales_acquisitions"] == 0
    assert result["status"] == "NO_CANONICAL_SALES_ACQUISITIONS_IN_OWNER_READ"


def test_missing_receipt_is_unknown_not_zero(tmp_path):
    result=observe_owner_sales(tmp_path,now=NOW)
    assert result["canonical_sales_acquisitions"] is None
    assert result["status"].startswith("HELD")


def test_forgeries_and_counter_inconsistency_held():
    for field,value in (
        ("generated_at_utc",(NOW-timedelta(days=3)).isoformat()),
        ("source_schema_version","fake"),
        ("source_status","verified_revenue"),
        ("read_only",False),
        ("execution_authority","send"),
        ("source_evidence_consistent_rows",5),
        ("founder_binding_exact_one_rows",0),
        ("visible_commercial_sales_prospects",2),
        ("sales_acquisition_rows",0),
    ):
        bogus=packet()
        bogus[field]=value
        result=public_review(bogus,now=NOW)
        assert result["source_and_tenant_aggregate_valid"] is False,(field,result)


def test_no_privileged_operator_calls_for_unprivileged_caller(monkeypatch):
    monkeypatch.setattr(owner.os,"geteuid",lambda:1000)
    monkeypatch.setattr(owner,"run",
                        lambda: (_ for _ in ()).throw(AssertionError("ran DB query")))
    assert owner.publish_owner_read()["receipt_written"] is False


def test_user_created_receipt_is_rejected(tmp_path):
    target=tmp_path/RECEIPT
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(packet()))
    # A synthetic user-owned receipt is never DBA evidence.
    result=observe_owner_sales(tmp_path,now=NOW)
    assert result["canonical_sales_acquisitions"] is None
