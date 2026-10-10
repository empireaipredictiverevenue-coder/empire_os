"""Inspect previously saved source reviews without rerunning searches or exposing PII."""
import json
from pathlib import Path

import pytest
from scripts.summarize_saved_tam_source_review import aggregate, classify_saved


def packet(findings):
    return {
       "schema_version":"empire.tam-first-party-discovery-review.v1",
       "source":"first_party_search","mode":"OBSERVE",
       "database_write":False,"acquisitions_appended":0,
       "outbound_sent":False,"execution_authority":"none",
       "entities_selected_for_search":3,
       "search_candidates_before_cross_entity_filter":1,
       "website_probes_attempted":1,"findings":findings,
       "secret_password":"SHOULD_NEVER_OUTPUT",
    }


def test_existing_success_and_failures_are_distinguished_without_identifiers():
    document=packet([
       {"review_state":"AMBIGUOUS_OR_MISSING_DISCOVERED_HOST",
        "entity_id":"uuid-private-1","canonical_name":"Private Solar"},
       {"review_state":"AMBIGUOUS_OR_MISSING_DISCOVERED_HOST",
        "entity_id":"uuid-private-2"},
       {"review_state":"DISCOVERED_SITE_IDENTITY_UNVERIFIED",
        "entity_id":"uuid-private-3","canonical_name":"Secret Company",
        "source_url":None,"observed_business_names":[]},
    ])
    result=aggregate(document)
    assert result["breakdown"]=={
        "no_unique_website_candidate":2,
        "site_not_verified_from_expected_host":1,
    }
    assert result["site_probes_attempted"]==1
    assert result["new_network_calls"]==0
    assert result["new_database_queries"]==0
    assert result["new_database_writes"]==0
    assert result["country_verified"] is False
    serialized=json.dumps(result)
    for secret in ("uuid-private", "Private Solar","Secret Company",
                   "SHOULD_NEVER_OUTPUT","https://private-site.example"):
        assert secret not in serialized


def test_retrieved_site_but_not_matched_is_distinct_without_revealing_url():
    result=aggregate(packet([
       {"review_state":"AMBIGUOUS_OR_MISSING_DISCOVERED_HOST"},
       {"review_state":"AMBIGUOUS_OR_MISSING_DISCOVERED_HOST"},
       {"review_state":"DISCOVERED_SITE_IDENTITY_UNVERIFIED",
        "source_url":"https://private-site.example/",
        "observed_business_names":["another private name"]},
    ]))
    assert result["breakdown"]=={
        "no_unique_website_candidate":2,
        "site_retrieved_but_identity_not_corroborated":1,
    }
    assert "private-site" not in str(result)
    assert "another private" not in str(result)


def test_supported_review_state_is_still_held_without_claiming_acquisition():
    result=aggregate(packet([
       {"review_state":"DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW",
        "canonical_name":"private","source_url":"https://private.test"},
    ]))
    assert result["breakdown"]=={
        "company_name_supported_review_only":1
    }
    assert result["acquisitions_appended"]==0


@pytest.mark.parametrize("change",[
    {"schema_version":"empire.unknown"},
    {"source":"fake"},
    {"database_write":True},
    {"acquisitions_appended":1},
    {"outbound_sent":True},
    {"execution_authority":"send"},
    {"website_probes_attempted":6},
    {"findings":[{"review_state":"UNKNOWN"}]},
])
def test_no_unsafe_or_unrecognised_packets(change):
    doc=packet([])
    doc.update(change)
    with pytest.raises(ValueError):
        aggregate(doc)


def test_filename_validation_and_no_traversal(tmp_path):
    filename="20261010T200046Z-3e7726d663ba.json"
    (tmp_path/filename).write_text(json.dumps(packet([
        {"review_state":"DISCOVERED_SITE_IDENTITY_UNVERIFIED",
         "source_url":None},
    ])))
    (tmp_path/filename).chmod(0o600)
    assert classify_saved(filename,tmp_path)["site_probes_attempted"]==1
    for malformed in ("../etc/passwd","review.json",
                      "20261010T200046Z-3e7726d663baXjson",
                      "20261010T200046Z-3e7726d663ba.json/other"):
        with pytest.raises(ValueError):
            classify_saved(malformed,tmp_path)


def test_reject_world_readable_or_symlinked_sensitive_files(tmp_path):
    name="20261010T200046Z-3e7726d663ba.json"
    file=tmp_path/name
    file.write_text(json.dumps(packet([])))
    file.chmod(0o644)
    with pytest.raises(ValueError):
        classify_saved(name,tmp_path)
    file.chmod(0o600)
    target=tmp_path/"elsewhere.json"
    target.write_text(json.dumps(packet([])))
    file.unlink()
    file.symlink_to(target)
    with pytest.raises(ValueError):
        classify_saved(name,tmp_path)
