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


def test_official_uk_private_research_source_receipt_is_digest_bound_and_held(packet):
    from hashlib import sha256
    from datetime import datetime
    row = next(x for x in packet["records"] if x["domain"] == "ich-services.co.uk")
    source = row["official_uk_source_observation"]
    assert source["schema_version"] == "empire.predictive_cloud.official_source_research.v1"
    assert source["source_kind"] == "independent_uk_public_company_register"
    assert source["source_url"] == (
        "https://find-and-update.company-information.service.gov.uk/company/02745893"
    )
    fields = source["public_register_fields"]
    assert fields["company_number"] == "02745893"
    assert fields["company_name"] == "ICH SERVICES LTD"
    assert fields["company_status"] == "Active"
    assert fields["sic_codes"] == ["43210", "43220", "81100"]
    assert source["source_evidence_digest"] == sha256(
        json.dumps(fields,sort_keys=True,separators=(",", ":")).encode()
    ).hexdigest()
    assert len(bytes.fromhex(source["official_response_sha256"])) == 32
    assert source["official_response_bytes"] >= 10000
    observed = datetime.fromisoformat(source["source_observed_at_utc"])
    assert observed.tzinfo is not None and observed.utcoffset() is not None
    assert source["permitted_purpose_candidate"] == "PRIVATE_PREDICTIVE_RESEARCH_ONLY"
    assert source["public_register_reuse_policy"] == "REUSE_PERMITTED_SUBJECT_TO_APPLICABLE_LAW"
    for gate in (
        "source_rights_document_has_been_owner_attested",
        "original_signed_crm_tenant_bound",
        "restricted_empiredb_rights_reader_verified",
        "production_source_admitted",
        "redis_publish_authorized",
        "customer_forecast_verified",
        "customer_delivery_authorized",
        "paid_provider_call",
    ):
        assert source[gate] is False
    assert source["execution_authority"] == "none"
    assert packet["provenance_controls"]["source_admitted_into_predictive_cloud"] is False


def test_texas_open_data_source_licence_unknown_even_when_official_licence_observed(packet):
    tex = next(x for x in packet["source_rights"]
               if x["source"] == "Texas TDLR open-data licence register")
    assert tex["dataset_license_listing"] == "unspecified"
    assert tex["source_license_for_external_resale_verified"] is False
    row = next(x for x in packet["records"] if x["domain"] == "kahnmechanical.com")
    assert row["independent_texas_regulator_snapshot"]["verified_from_official_dataset"]
    assert row["customer_delivery_authorized"] is False


def test_official_source_preparation_fails_on_wrong_identity_or_changed_status():
    import importlib.util
    source_file = (
        Path(__file__).resolve().parents[1]
        / "scripts/prepare_official_registry_held_source_20261108.py"
    )
    spec = importlib.util.spec_from_file_location("held_source_preparer", source_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    valid = (
        "ICH SERVICES LTD 02745893 Company status Active "
        "Union Bridge Works Roker Lane Incorporated on 9 September 1992 "
        "43210 43220 81100"
    ).encode()
    assert module.company_page_facts(valid) is None
    with pytest.raises(ValueError, match="official_company_page_fact_not_observed"):
        module.company_page_facts(valid.replace(b"Company status Active", b"Company status Dissolved"))
    with pytest.raises(ValueError, match="official_company_page_fact_not_observed"):
        module.company_page_facts(valid.replace(b"02745893", b"00000000"))


def test_original_review_packet_preimage_fence_refuses_second_unapproved_rewrite():
    import importlib.util
    source_file = (
        Path(__file__).resolve().parents[1]
        / "scripts/prepare_official_registry_held_source_20261108.py"
    )
    spec = importlib.util.spec_from_file_location("held_source_preparer_replay",source_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="original_evidence_packet_preimage_changed"):
        module.run(apply_existing_packet=True)
