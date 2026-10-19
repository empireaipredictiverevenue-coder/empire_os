"""Regressions for legacy US scanners and governance of existing sources."""
import pytest
from empire_os.scanner_source_contract_bridge import review_existing_scanner_rows

def item(**overrides):
    r = {
        "source": "recc_solar",
        "url": "https://www.recc.org.uk/scheme/members/solar-firm",
        "name": "Acme Solar Ltd",
        "niche": "solar",
        "entity_kind": "business",
        "contains_consumer_claimant_or_patient_data": False,
    }
    r.update(overrides)
    return r

def run(rows=None, **kwargs):
    defaults = dict(
        niche="solar", target_kind="contractor", territory="GB-ENG",
        rights_receipt_ref="source_review:synthetic-20261019",
    )
    defaults.update(kwargs)
    return review_existing_scanner_rows(
        [item()] if rows is None else rows, **defaults
    )

def test_existing_governed_registry_offline_source_review():
    result = run()
    assert result["source_review_counts"] == {"OFFLINE_SOURCE_REVIEW": 1}
    assert result["canonical_empiredb_writes"] is False
    assert result["outbound_authorized"] is False
    row = result["observations"][0]
    assert row["source_id"] == "gb_recc_solar"
    assert row["canonical_business_verified"] is False
    assert row["waterfall_enrich_authorized"] is False

@pytest.mark.parametrize("legacy_source", [
    "dbpr", "sunbiz", "county-appraiser", "permits", "bbb",
    "web-search", "reddit",
])
def test_legacy_scanner_sources_not_rebranded_as_verified(legacy_source):
    row = run([item(source=legacy_source)])["observations"][0]
    assert row["review_state"] == "HOLD"
    assert "source_contract_not_registered_or_verified" in row["reasons"]

@pytest.mark.parametrize("bad", [
    {"url": "https://some-other-registry.example/members"},
    {"url": "http://www.recc.org.uk/scheme/members"},
    {"url": "https://www.recc.org.uk:443/members"},
    {"entity_kind": "person"},
    {"contains_consumer_claimant_or_patient_data": True},
    {"contains_consumer_claimant_or_patient_data": None},
    {"name": ""},
])
def test_company_identity_and_source_origin_required(bad):
    result = run([item(**bad)])
    assert result["observations"][0]["review_state"] == "HOLD"

def test_regulated_law_and_insurance_never_relabelled_as_open_prospect():
    r = run([item(source="gb_companies_house",
                  url="https://api.company-information.service.gov.uk/company/123")],
            niche="mass_torts", target_kind="law_firm")
    assert r["observations"][0]["review_state"] == "HOLD"
    assert "regulated_b2b_jurisdiction_review_required" in r["observations"][0]["reasons"]
    assert r["observations"][0]["claimant_profiling_authorized"] is False

def test_duplicate_scan_record_goes_to_hold():
    r = run([item(), item()])
    assert r["source_review_counts"] == {
        "HOLD": 1, "OFFLINE_SOURCE_REVIEW": 1
    }
    assert "duplicate_observation_same_scan" in r["observations"][1]["reasons"]

def test_missing_source_rights_receipt_is_held():
    r = run(rights_receipt_ref="")
    assert "source_rights_receipt_missing" in r["observations"][0]["reasons"]

def test_mismatched_country_is_held():
    r = run(territory="US-TX")
    assert "source_territory_mismatch" in r["observations"][0]["reasons"]

def test_unbounded_legacy_scanner_rows_are_rejected():
    with pytest.raises(ValueError):
        run([item(name=f"Company {i}") for i in range(41)])
