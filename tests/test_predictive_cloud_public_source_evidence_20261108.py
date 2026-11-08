"""Evidence-contract checks for the already-owned Data Cloud/PPIR source lane.

All records are research-only. Does not fetch, scrape, ingest, bill or contact.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

PACKET = (
    Path(__file__).resolve().parents[1]
    / "docs/PREDICTIVE_CLOUD_FIRST_PARTY_RESEARCH_COHORT_20261108.json"
)


@pytest.fixture
def packet():
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_fixed_original_search_cohort_reconciled_without_promoting_raw_rows(packet):
    assert packet["schema_version"] == "empire.predictive_cloud.first_party_research_cohort.v1"
    assert packet["mode"] == "RESEARCH_ONLY"
    assert packet["execution_authority"] == "none"
    assert packet["raw_source_candidates"] == 4
    assert len(packet["records"]) == 4
    assert packet["original_search_fabric_policy_review"]["eligible_research_only"] == 2
    assert packet["original_search_fabric_policy_review"]["rejected"] == 2
    assert {r["domain"] for r in packet["records"] if r["research_policy"] == "PASS_RESEARCH_ONLY"} == {
        "kahnmechanical.com", "ich-services.co.uk"
    }
    assert {r["domain"] for r in packet["records"] if r["research_policy"] == "REJECTED"} == {
        "cedur.com", "ziprecruiter.com"
    }


def test_official_texas_regulator_observation_is_snapshot_not_current_authority(packet):
    row = next(x for x in packet["records"] if x["domain"] == "kahnmechanical.com")
    s = row["independent_texas_regulator_snapshot"]
    assert s["verified_from_official_dataset"] is True
    assert s["business_name"] == "KAHN A/C & HEATING COMPANY A TEXAS CORP"
    assert s["license_type"] == "A/C Contractor"
    assert s["license_number"] == "16607"
    assert s["license_expiration_date"] == "2027-04-12"
    assert s["dataset_last_updated"] == "2026-09-19"
    assert s["current_license_status_verified"] is False
    assert s["business_brand_to_legal_entity_link_verified"] is False
    assert s["customer_redistribution_rights_verified"] is False
    assert urlparse(s["source_url"]).hostname == "data.texas.gov"
    assert row["independent_legal_identity_verified"] is False


def test_uk_company_register_and_first_party_website_cross_corroboration(packet):
    row = next(x for x in packet["records"] if x["domain"] == "ich-services.co.uk")
    assert row["public_register_match"] is True
    assert row["website_control_cryptographically_verified"] is False
    assert set(row["website_register_cross_correlated_by"]) >= {
        "business_name", "predecessor_name", "registered_address"
    }
    assert row["contact_consent_verified"] is False
    assert any(
        f["source_kind"] == "official_uk_company_register"
        and f["source_url"].endswith("/02745893")
        for f in row["observed_business_facts"]
    )


def test_no_unreviewed_customer_data_or_decodo_licence_promotion(packet):
    assert all(r["customer_delivery_authorized"] is False for r in packet["records"])
    assert all(r.get("independent_legal_identity_verified") is not True
               or r["domain"] == "ich-services.co.uk" for r in packet["records"])
    decodo = next(x for x in packet["source_rights"] if x["source"] == "Decodo")
    assert decodo["competing_product_restriction_present"] is True
    assert decodo["account_specific_written_exception_observed"] is False
    assert decodo["customer_data_redistribution_authorized"] is False
    assert decodo["approved_paid_calls"] == 0
    p = packet["provenance_controls"]
    assert p["source_page_sha256_captured"] is False
    assert p["contains_pii"] is False
    assert p["source_admitted_into_predictive_cloud"] is False
    assert p["postgres_mutation"] is False
    assert p["paid_provider_calls"] is False


def test_sources_use_public_https_links_and_no_personal_data(packet):
    for row in packet["records"]:
        assert "@" not in row["domain"]
        for f in row.get("observed_business_facts", ()):
            assert urlparse(f["source_url"]).scheme == "https"
            assert urlparse(f["source_url"]).hostname is not None
    assert packet["next_release_gate"] == (
        "ORIGINAL_SEARCH_FABRIC_SOURCE_RIGHTS_OWNER_AND_PREDICTIVE_SOURCE_ADMISSION"
    )
