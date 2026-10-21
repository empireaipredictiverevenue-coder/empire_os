"""Original owned URLs: genuine source observations, never ground truth."""
from copy import deepcopy
from pathlib import Path

import pytest

from empire_os.search_intelligence.jev_evidence_intake import (
    JevEvidenceIntakeHeld, build_original_page_review_intake, intake_summary_only,
)


def source_fixture():
    items = [
        ("/aeo/empire/ai_lead_gen/", "EMPIRE_PRODUCT_TOPIC_REVIEW", 4, 0),
        ("/aeo/roofing/PVD/", "ROOFING_RESEARCH_REVIEW", 1, 0),
    ]
    rows = []
    for path, cat, impressions, clicks in items:
        rows.append({
            "path": path, "review_category": cat,
            "review_action": "VERIFY_ORIGINAL_PAGE_CONTENT",
            "page_dimension_impressions": impressions,
            "page_dimension_clicks": clicks, "origin_http_status": 404,
            "publisher_rights_verified": False,
            "current_page_equivalence_verified": False,
            "restore_authorized": False, "redirect_authorized": False,
            "revenue_verified": False,
        })
    return {
        "schema_version": "empire.organic_search.gsc_page_legacy_404_review.v1",
        "status": "REVIEW_MISSING_LEGACY_URLS",
        "mode": "OBSERVE",
        "source": "google_search_console_page_dimension_final",
        "site_url": "sc-domain:empire-ai.co.uk",
        "window": ["2026-10-07", "2026-10-19"],
        "returned_page_totals_are_sitewide": False,
        "query_page_rows_joined_or_added": False,
        "redirect_authorized": False, "publication_authorized": False,
        "buyer_conversion_verified": False, "revenue_verified": False,
        "outbound_sent": False, "database_writes": False,
        "execution_authority": "none",
        "returned_page_rows": 4,
        "missing_legacy_page_count": len(rows),
        "missing_review_queue": rows,
        "missing_legacy_page_impressions": 5,
        "missing_legacy_page_clicks": 0,
        "missing_review_categories": {
            "EMPIRE_PRODUCT_TOPIC_REVIEW": 1,
            "ROOFING_RESEARCH_REVIEW": 1,
        },
    }


def test_original_url_candidate_intake_has_no_fake_labels():
    data = build_original_page_review_intake(source_fixture())
    assert data["schema_version"] == "empire.search.jev_original_page_review_intake.v1"
    assert data["observed_missing_case_count"] == 2
    assert data["accepted_human_ground_truth_labels"] == 0
    assert data["independently_labelled_case_count"] == 0
    assert data["benchmark_ready_case_count"] == 0
    assert data["comparison_with_aggregate_jev_one_shot_permitted"] is False
    assert data["input_source_rights_to_train_verified"] is False
    assert data["external_jev_inference_performed"] is False
    assert data["publication_authorized"] is False
    assert data["automatic_redirects_authorized"] is False
    assert data["database_writes"] is False
    assert data["execution_authority"] == "NONE"
    ids = [x["case_id"] for x in data["deduplicated_original_cases"]]
    assert len(ids) == len(set(ids))
    assert all(x["proposed_human_review_label"] is None for x in data["deduplicated_original_cases"])
    assert all(x["reviewer_identity_authenticated"] is False for x in data["deduplicated_original_cases"])
    assert all(x["independent_jev_case_evaluation_ready"] is False for x in data["deduplicated_original_cases"])
    assert all(x["source_ref"].startswith("gsc-page-origin-sha256:") for x in data["deduplicated_original_cases"])


def test_idempotent_case_keys_for_same_real_evidence():
    a = build_original_page_review_intake(source_fixture())
    b = build_original_page_review_intake(source_fixture())
    assert [x["case_id"] for x in a["deduplicated_original_cases"]] == [
        x["case_id"] for x in b["deduplicated_original_cases"]]


@pytest.mark.parametrize("key, value", [
    ("mode", "PUBLISH"),
    ("source", "site:quora.com"),
    ("site_url", "sc-domain:other.com"),
    ("returned_page_totals_are_sitewide", True),
    ("query_page_rows_joined_or_added", True),
    ("redirect_authorized", True),
    ("publication_authorized", True),
    ("buyer_conversion_verified", True),
    ("revenue_verified", True),
    ("outbound_sent", True),
    ("database_writes", True),
    ("execution_authority", "publish"),
])
def test_source_policy_cannot_be_silently_escalated(key, value):
    src = source_fixture()
    src[key] = value
    with pytest.raises(JevEvidenceIntakeHeld, match="SOURCE_CONTRACT"):
        build_original_page_review_intake(src)


@pytest.mark.parametrize("path", [
    "https://evil.example/aeo/roofing/PVD/",
    "//evil.example/aeo/roofing/PVD/",
    "/aeo/roofing/PVD/?contact=a",
    "/aeo/roofing/../../admin/",
    "/aeo/roofing/AA\\secret",
])
def test_external_or_injected_paths_are_rejected(path):
    src = source_fixture()
    src["missing_review_queue"][0]["path"] = path
    with pytest.raises(JevEvidenceIntakeHeld, match="URL_NOT_ALLOWLISTED"):
        build_original_page_review_intake(src)


def test_trailing_slash_url_alias_is_duplicate():
    src = source_fixture()
    src["missing_review_queue"][1]["path"] = "/aeo/empire/ai_lead_gen"
    with pytest.raises(JevEvidenceIntakeHeld, match="DUPLICATE"):
        build_original_page_review_intake(src)


def test_inconsistent_sample_counts_fail_closed():
    src = source_fixture()
    src["missing_legacy_page_impressions"] += 100
    with pytest.raises(JevEvidenceIntakeHeld, match="AGGREGATE_MISMATCH"):
        build_original_page_review_intake(src)


def test_private_summary_exposes_no_full_url_path_or_raw_queries():
    src = source_fixture()
    src["raw_search_queries"] = ["customer private query"]
    data = build_original_page_review_intake(src)
    summary = intake_summary_only(data)
    assert summary["observed_url_case_count"] == 2
    assert summary["reviewed_human_labels"] == 0
    assert "ai_lead_gen" not in str(summary)
    assert "customer private query" not in str(summary)
    assert summary["execution_authority"] == "NONE"


def test_unsupported_human_label_in_source_cannot_count_as_verified():
    src = source_fixture()
    src["missing_review_queue"][0]["human_label"] = "PUBLISH_NOW"
    data = build_original_page_review_intake(src)
    assert data["accepted_human_ground_truth_labels"] == 0
    assert data["deduplicated_original_cases"][0]["proposed_human_review_label"] is None


def test_review_state_tamper_is_rejected():
    summary = build_original_page_review_intake(source_fixture())
    summary["accepted_human_ground_truth_labels"] = 999
    with pytest.raises(JevEvidenceIntakeHeld):
        intake_summary_only(summary)
