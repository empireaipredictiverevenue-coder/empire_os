"""Held Analytics075 taxonomy and canonical CRM/Finance lineage contract.

ALL row data here is SYNTHETIC TEST DATA. Never submitted to a provider/DB.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import pytest

from empire_os.analytics.acquisition_source_v2_candidate import (
    ALL_EVIDENCE, ORIGINAL_EVIDENCE, PROPOSED_EVIDENCE,
    review_acquisition_source_candidate,
)
from empire_os.analytics.canonical_commercial_lineage import review_owner_source_to_cash

ROOT = Path(__file__).resolve().parents[2]
TENANT = "0e8e7afd-85ed-482d-b508-9175a152cf22"
WINDOW = {
    "window_start_utc": "2026-10-01T00:00:00+00:00",
    "window_end_utc": "2026-10-02T00:00:00+00:00",
}


def _base(schema, owner, **values):
    return {
        "schema_version": schema, "mode": "READ_ONLY",
        "canonical_tenant_id": TENANT,
        "property_key": "empire-ai.co.uk",
        "source_cohort_ref": "test_cohort_october_2026",
        "acquisition_channel": "organic_search", **WINDOW,
        "original_reader_source": owner,
        "owner_evidence_ref": "synthetic_receipt_20261027",
        "authenticated_original_owner_assertion": True,
        "execution_authority": "NONE",
        **values,
    }


def synthetic_owners():
    return {
        "analytics": _base(
            "empire.analytics.original_collection_owner_cohort.v1",
            "ORIGINAL_ANALYTICS_TENANT_AGGREGATE_READER",
            observed_consented_sessions=30, observed_cta_sessions=15,
            lawful_analytics_consent_verified=True,
            trusted_source_classification_verified=True,
        ),
        "crm": _base(
            "empire.crm.original_accepted_order_cohort.v1",
            "ORIGINAL_CRM_TENANT_ACCEPTED_ORDER_READER",
            accepted_order_count=8, source_linked_orders=7,
            independent_source_order_join_verified=True,
        ),
        "finance": _base(
            "empire.finance.original_settlement_cohort.v1",
            "ORIGINAL_FINANCE_SETTLEMENT_READER",
            settled_order_count=5, actual_cash_received_minor_units=250000,
            verified_source_cost_minor_units=25000, currency_code="GBP",
            settlement_finality_verified=True, refunds_reconciled=True,
            costs_reconciled=True,
        ),
    }


def test_original_v1_and_proposed_v2_channels_have_distinct_source_proofs():
    assert len(ORIGINAL_EVIDENCE) == 6
    assert len(PROPOSED_EVIDENCE) == 5
    assert len(ALL_EVIDENCE) == 11
    assert set(ORIGINAL_EVIDENCE).isdisjoint(PROPOSED_EVIDENCE)
    for name, proof in ALL_EVIDENCE.items():
        report = review_acquisition_source_candidate(
            channel=name, source_evidence_kind=proof
        )
        assert report["new_schema_release_required"] == (name in PROPOSED_EVIDENCE)
        assert report["v2_database_migration_deployed_verified"] is False
        assert report["source_attribution_authorized"] is False
        assert report["media_spend_authorized"] is False
        assert report["execution_authority"] == "NONE"
    for name, proof in PROPOSED_EVIDENCE.items():
        assert name in ("paid_search", "paid_social", "affiliate_partner",
                        "publisher_referral", "organic_video")
        assert proof != "server_unknown"


@pytest.mark.parametrize("channel,proof", [
    ("paid_search", "server_verified_referral"),
    ("affiliate_partner", "signed_campaign_binding"),
    ("paid_social", "browser_utm_parameter"),
    ("google_cpc_email_a", "signed_campaign_binding"),
    ("phone_inbound", "signed_campaign_binding"),
    ("organic_video", "signed_partner_binding"),
    ("referral", "signed_partner_binding"),
])
def test_paid_or_partner_source_cannot_be_laundered_into_organic(channel, proof):
    with pytest.raises(ValueError):
        review_acquisition_source_candidate(
            channel=channel, source_evidence_kind=proof
        )


def test_source_receipt_even_owner_asserted_is_not_authenticated_here():
    item = review_acquisition_source_candidate(
        channel="affiliate_partner", source_evidence_kind="signed_partner_binding",
        authenticated_owner_receipt={
            "verified_by_original_server_owner": True,
            "owner_reader_source": "ORIGINAL_ANALYTICS_AUTHENTICATED_SOURCE_READER",
            "property_bound": True,
            "privacy_source_purpose_approved": True,
        },
    )
    assert item["original_owner_source_attestation_asserted"] is True
    assert item["owner_receipt_independently_authenticated_by_this_function"] is False
    assert item["source_attribution_authorized"] is False
    with pytest.raises(ValueError):
        review_acquisition_source_candidate(
            channel="paid_search", source_evidence_kind="signed_campaign_binding",
            authenticated_owner_receipt={"browser_consent": True},
        )


def test_held_migration_requires_owner_and_original_erasure_and_no_runtime_grant():
    script = (ROOT / "migrations/empiredb/075_first_party_analytics_source_taxonomy_v2_held.sql").read_text()
    assert "ANALYTICS075_ERASURE_OWNER_NOT_READY" in script
    assert "ANALYTICS075_UNSAFE_MIGRATOR" in script
    assert "ANALYTICS075_V1_BASE_CONSTRAINTS_CHANGED" in script
    assert "FORCE ROW LEVEL SECURITY" not in script  # relies on verified existing RLS
    assert "NOT VALID" in script and "VALIDATE CONSTRAINT" in script
    assert script.count("COMMIT;") == 1
    assert "GRANT " not in script.upper()
    assert "CREATE ROLE" not in script.upper()
    assert "CREATE POLICY" not in script.upper()
    assert "INSERT INTO" not in script.upper()
    assert "DROP TABLE" not in script.upper()
    for channel in ALL_EVIDENCE:
        assert "'" + channel + "'" in script
    for proof in set(ALL_EVIDENCE.values()):
        assert "'" + proof + "'" in script


def test_no_evidence_is_held_without_any_executing_side_effect():
    report = review_owner_source_to_cash()
    assert report["status"] == "HOLD_ORIGINAL_OWNER_EVIDENCE_INCOMPLETE"
    assert len(report["missing_original_owner_proofs"]) == 3
    assert report["database_queries_executed"] is False
    assert report["ingress_or_collector_activated"] is False
    assert report["verified_cash_margin_minor_units"] is None


def test_synthetic_three_owner_match_is_still_not_independently_verified_cash():
    inputs = synthetic_owners()
    report = review_owner_source_to_cash(**inputs)
    assert report["status"] == "ALL_ORIGINAL_OWNER_ASSERTIONS_PRESENT_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert all(report["owner_assertion_gates"].values())
    assert report["verified_revenue_minor_units"] is None
    assert report["verified_cash_margin_minor_units"] is None
    assert report["source_to_crm_conversion_independently_proven_by_this_review"] is False
    assert report["source_to_finance_cash_independently_proven_by_this_review"] is False
    assert report["eligible_for_predictive_revenue_training"] is False
    assert report["crm_writes"] is False and report["finance_writes"] is False
    assert "250000" not in json.dumps(report)
    assert TENANT not in json.dumps(report)
    assert "synthetic_receipt_20261027" not in json.dumps(report)


@pytest.mark.parametrize("owner,field,bad", [
    ("analytics", "canonical_tenant_id", "0e8e7afd-85ed-482d-b508-9175a152cf23"),
    ("crm", "source_cohort_ref", "other_cohort_20261027"),
    ("finance", "window_end_utc", "2026-10-03T00:00:00Z"),
    ("finance", "acquisition_channel", "email"),
    ("finance", "property_key", "other.example"),
])
def test_cross_tenant_and_source_window_collisions_fail_closed(owner,field,bad):
    data = synthetic_owners()
    data[owner][field] = bad
    with pytest.raises(ValueError):
        review_owner_source_to_cash(**data)


@pytest.mark.parametrize("owner,field,bad", [
    ("analytics","user_email","a@b.example"),
    ("analytics","observed_cta_sessions",31),
    ("analytics","lawful_analytics_consent_verified","true"),
    ("crm","buyer_phone","+18880000000"),
    ("crm","source_linked_orders",9),
    ("finance","raw_bank_account","12345"),
    ("finance","actual_cash_received_minor_units",True),
    ("finance","settled_order_count",9),
    ("finance","currency_code","USDT"),
    ("finance","verified_source_cost_minor_units",-1),
])
def test_pii_bad_stage_and_currency_are_rejected(owner,field,bad):
    data=synthetic_owners()
    data[owner][field]=bad
    with pytest.raises(ValueError):
        review_owner_source_to_cash(**data)


def test_original_readers_missing_authority_do_not_promote_metrics():
    data=synthetic_owners()
    data["finance"]["settlement_finality_verified"]=False
    data["crm"]["authenticated_original_owner_assertion"]=False
    r=review_owner_source_to_cash(**data)
    assert not r["owner_assertion_gates"]["original_crm_accepted_order_read"]
    assert not r["owner_assertion_gates"]["original_finance_cash_and_cost_read"]
    assert r["verified_revenue_minor_units"] is None
    assert r["status"]=="HOLD_ORIGINAL_OWNER_EVIDENCE_INCOMPLETE"
