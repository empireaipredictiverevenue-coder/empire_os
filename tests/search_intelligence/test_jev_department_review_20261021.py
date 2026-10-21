"""Higher-level SEO Jev task board: actual bounded aggregates, no model use."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.jev_department_review import (
    SCALAR_FIELDS, LANES, JevDepartmentEvidenceError,
    review_jev_department_portfolio,
)
from empire_os.search_intelligence.quora_intelligence import review_quora_research
from empire_os.search_intelligence.service import build_search_intelligence_service


def fixture_department():
    # Synthetic TEST fixture, never presented as a live sourced observation.
    counts = {field: 0 for field in SCALAR_FIELDS}
    counts.update({
        "gsc_returned_page_rows": 32,
        "gsc_returned_page_sample_impressions": 64,
        "legacy_missing_404_count_in_returned_page_sample": 30,
        "legacy_missing_404_impressions_in_returned_page_sample": 44,
        "legacy_404_core_topic_editorial_review_count": 15,
        "legacy_404_off_core_retain_404_count": 15,
        "search_fabric_cache_files_observed": 1896,
        "search_fabric_cache_stale_candidates": 1801,
        "search_fabric_cache_fresh_candidates_24h": 91,
        "search_fabric_cache_invalid_envelopes": 4,
        "semantic_live_priority_pages_checked": 4,
        "semantic_editorial_review_candidates": 2,
        "growth_specialist_desks": 8,
        "research_campaigns": 9,
    })
    return {
        "schema_version": "empire.search_growth.department_integration.v1",
        "status": "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN",
        "mode": "OBSERVE",
        "execution_authority": "NONE",
        "customer_identifiers_disclosed": False,
        "publisher_mutation_authorized": False,
        "search_rankings_verified": False,
        "external_ai_answer_citation_verified": False,
        "external_geo_mentions_verified": False,
        "buyer_enquiries_verified": False,
        "realised_revenue_verified": False,
        "independent_google_rank_positions_verified": False,
        "gsc_final_page_window": ["2026-10-07", "2026-10-19"],
        **counts,
    }


def test_high_level_tasks_use_existing_department_owner_and_typed_questions():
    p = review_jev_department_portfolio(fixture_department(), review_quora_research())
    assert p["task_count"] == len(LANES) == 14
    assert p["aggregate_observed_lane_count"] == 5
    assert p["independent_case_evaluation_ready_count"] == 0
    assert len({x["task_id"] for x in p["task_board"]}) == 14
    assert p["scope"] == "EXISTING_SEO_DEPARTMENT"
    assert all(x["existing_owner"] for x in p["task_board"])
    assert all(set(x["questions"]) == {
        "recommended_queue", "review_priority", "human_review_required",
    } for x in p["task_board"])
    assert all(x["questions"]["recommended_queue"]["type"] == "choice" for x in p["task_board"])
    assert all(x["questions"]["review_priority"]["type"] == "score" for x in p["task_board"])
    assert all(x["questions"]["human_review_required"]["type"] == "noul" for x in p["task_board"])
    assert all(x["jev_prediction"] is None and x["jev_score"] is None
               and x["jev_confidence"] is None for x in p["task_board"])
    assert p["jev_inference_calls"] == p["jev_scores_generated"] == 0
    assert p["provider_keys_accessed"] is False
    assert p["external_requests_performed_by_review"] is False
    assert p["buyer_outreach_authority"] is False
    assert p["database_writes"] is False
    assert p["execution_authority"] == "NONE"


def test_real_existing_aggregate_work_not_exaggerated_to_verified_outcomes():
    p = review_jev_department_portfolio(fixture_department(), review_quora_research())
    lanes = {x["task_id"]: x for x in p["task_board"]}
    assert lanes["GSC_404_RECOVERY"]["aggregate_scalar_evidence"][
        "legacy_missing_404_count_in_returned_page_sample"] == 30
    assert lanes["SEARCH_FABRIC_FRESHNESS"]["aggregate_scalar_evidence"][
        "search_fabric_cache_stale_candidates"] == 1801
    assert lanes["ORIGINAL_CONTENT_QUALITY"]["aggregate_scalar_evidence"][
        "semantic_editorial_review_candidates"] == 2
    assert lanes["AEO_CITATION_COVERAGE"]["evidence_state"] == "ORIGINAL_EVIDENCE_REQUIRED"
    assert lanes["GEO_ENTITY_VISIBILITY"]["evidence_state"] == "ORIGINAL_EVIDENCE_REQUIRED"
    assert lanes["INDEPENDENT_SERP_COMPETITION"]["evidence_state"] == "ORIGINAL_EVIDENCE_REQUIRED"
    assert lanes["ORGANIC_COMMERCIAL_ATTRIBUTION"]["evidence_state"] == "ORIGINAL_EVIDENCE_REQUIRED"
    assert p["estimated_business_value"] is None
    assert p["revenue_observed_from_jev"] is False


def test_sensitive_raw_data_does_not_appear_in_portfolio_response():
    raw = fixture_department()
    raw.update({
        "customer_email": "private.reviewer@example.test",
        "raw_query_rows": [{"query": "secret customer issue"}],
        "api_key": "DO_NOT_EXPOSE",
        "open_gates": ["A_GATE"],
    })
    content = str(review_jev_department_portfolio(raw, review_quora_research()))
    assert "private.reviewer@" not in content
    assert "secret customer issue" not in content
    assert "DO_NOT_EXPOSE" not in content
    assert "A_GATE" not in content


@pytest.mark.parametrize("key, value", [
    ("mode", "EXECUTE"), ("status", "APPROVED"),
    ("execution_authority", "PUBLISH"), ("customer_identifiers_disclosed", True),
    ("publisher_mutation_authorized", True),
    ("independent_google_rank_positions_verified", True),
    ("external_ai_answer_citation_verified", True),
    ("external_geo_mentions_verified", True),
    ("buyer_enquiries_verified", True),
    ("realised_revenue_verified", True),
    ("gsc_returned_page_rows", True),
    ("search_fabric_cache_stale_candidates", -1),
])
def test_department_source_contract_fails_closed(key, value):
    raw = fixture_department()
    raw[key] = value
    with pytest.raises(JevDepartmentEvidenceError):
        review_jev_department_portfolio(raw, review_quora_research())


def test_contradictory_counts_and_unverified_quora_fail_closed():
    raw = fixture_department()
    raw["legacy_missing_404_count_in_returned_page_sample"] = 40
    with pytest.raises(JevDepartmentEvidenceError, match="INCONSISTENT"):
        review_jev_department_portfolio(raw, review_quora_research())
    q = deepcopy(review_quora_research())
    q["verified_quora_questions"] = 1
    with pytest.raises(JevDepartmentEvidenceError, match="QUORA_SOURCE"):
        review_jev_department_portfolio(fixture_department(), q)


def test_endpoint_read_only_and_failed_source_holds(monkeypatch):
    import empire_os.search_intelligence.jev_department_review as mod
    monkeypatch.setattr(mod, "read_department_snapshot", fixture_department)
    client = TestClient(build_search_intelligence_service())
    good = client.get("/v1/search/jev/department/review")
    assert good.status_code == 200
    assert good.headers["cache-control"] == "no-store"
    assert good.headers["x-content-type-options"] == "nosniff"
    assert good.json()["task_count"] == 14
    assert good.json()["jev_inference_calls"] == 0
    def broken():
        raise JevDepartmentEvidenceError("internal_secret_source")
    monkeypatch.setattr(mod, "read_department_snapshot", broken)
    bad = client.get("/v1/search/jev/department/review")
    assert bad.status_code == 503
    assert bad.json()["detail"] == "jev_department_review_source_unavailable"
    assert "internal_secret" not in str(bad.json())


def test_disabled_provider_cannot_be_called_from_high_level_review(monkeypatch):
    from empire_os.typed_decision_provider import DisabledTypedDecisionProvider
    monkeypatch.setattr(DisabledTypedDecisionProvider, "evaluate",
                        lambda *_a, **_k: pytest.fail("provider invoked"))
    p = review_jev_department_portfolio(fixture_department(), review_quora_research())
    assert p["jev_provider"] == "disabled"
