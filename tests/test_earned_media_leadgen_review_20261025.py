"""Real source-led B2B demand scoring and fail-closed revenue controls."""
import json
from pathlib import Path

from empire_os.earned_media_advisory_bridge import review
from empire_os.earned_media_leadgen_review import (
    DIST_SNAPSHOT, DEMAND_DOC, REQUESTS, review_lead_generation,
)
from tests.test_earned_media_advisory_bridge_20261025 import prepared, save


def _packet(tmp_path):
    root, pr = prepared(tmp_path)
    save(root, DEMAND_DOC, "\n".join(x["url"] for x in REQUESTS))
    doc = root / DIST_SNAPSHOT
    base = json.loads(doc.read_text())
    base["proposal_only"] = True
    base["human_review_queue"] = [
        {
            "company": "Example Enterprise",
            "canonical_prospect_id": "caeeb9de-c2d2-460d-b6e2-46b2819f50c4",
            "execution_authority": "none",
            "commercial_role": "RESEARCH_PROSPECT_NOT_VERIFIED_BUYER",
            "outreach_authorized": False,
            "commercial_authority_verified": False,
            "why_now_evidence": ["First-party research on data operations"],
            "product_match_state": "INFERRED_RESEARCH_FIT",
            "person_verified": True,
            "email_verified": False,
            "readiness_blockers": ["verified_demand_unknown"],
        },
        {
            "company": "Example Trades",
            "canonical_prospect_id": None,
            "execution_authority": "none",
            "commercial_role": "RESEARCH_PROSPECT_NOT_VERIFIED_BUYER",
            "outreach_authorized": False,
            "commercial_authority_verified": False,
            "why_now_evidence": ["First-party research on operational challenges"],
        },
    ]
    save(root, DIST_SNAPSHOT, base)
    return root, pr, review(root, pr_root=pr)


def test_two_direct_requests_brokered_one_and_researched_companies(tmp_path):
    root, pr, packet = _packet(tmp_path)
    result = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert result["status"] == "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE"
    assert result["counts"] == {
        "source_signal": 3, "researched_account": 2,
        "canonical_researched_account": 1,
        "unbound_researched_account": 1,
        "qualified_buyer": 0, "total": 5,
    }
    assert [x["priority_score"] for x in result["opportunities"]] == sorted(
        [x["priority_score"] for x in result["opportunities"]], reverse=True)
    assert sum(x["priority_score"] == 70 for x in result["opportunities"]) == 2
    assert all(x["expected_revenue"] is None for x in result["opportunities"])
    assert not any(x["outbound_authorized"] for x in result["opportunities"])
    assert result["pipeline_value_gbp_minor"] is None
    assert result["recognised_revenue_state"] == "NOT_QUERIED"
    assert result["crm_writes"] is False


def test_unknown_company_has_no_canonical_prospect_or_sales_authority(tmp_path):
    root, _, packet = _packet(tmp_path)
    result = review_lead_generation(packet, repo_root=root, distribution_root=root)
    unbound = next(x for x in result["opportunities"] if x["label"] == "Example Trades")
    assert unbound["lead_stage"] == "RESEARCHED_ACCOUNT_UNBOUND"
    assert unbound["existing_canonical_prospect_id"] is None
    assert "CANONICAL_PROSPECT_ID_MISSING" in unbound["blockers"]
    assert unbound["recommended_offer_code"] is None
    assert unbound["priority_score"] <= 25


def test_revenue_snapshot_hash_drift_holds(tmp_path):
    root, _, packet = _packet(tmp_path)
    p = root / DIST_SNAPSHOT
    d = json.loads(p.read_text())
    d["human_review_queue"].append(dict(d["human_review_queue"][0],
                                         company="Unexpected review"))
    save(root, DIST_SNAPSHOT, d)
    out = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert out["status"] == "HELD_SOURCE_OR_PACKET_INTEGRITY"
    assert out["reason_code"] == "REVENUE_DISTRIBUTION_CHANGED_SINCE_BRIDGE_REVIEW"
    assert out["opportunities"] == []


def test_missing_request_source_holds_rather_than_inventing_demand(tmp_path):
    root, _, packet = _packet(tmp_path)
    save(root, DEMAND_DOC, REQUESTS[0]["url"])
    out = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert out["reason_code"] == "ORIGINAL_B2B_REQUEST_REFERENCES_CHANGED"
    assert out["counts"]["qualified_buyer"] == 0


def test_untrusted_review_packet_holds(tmp_path):
    root, _, packet = _packet(tmp_path)
    packet["new_outbound_authorized"] = True
    assert review_lead_generation(packet, repo_root=root, distribution_root=root)[
        "reason_code"] == "ORIGINAL_BRIDGE_PACKET_UNTRUSTED"


def test_false_claim_of_outreach_authority_row_skipped(tmp_path):
    root, _, packet = _packet(tmp_path)
    p = root / DIST_SNAPSHOT
    d = json.loads(p.read_text())
    d["human_review_queue"][0]["outreach_authorized"] = True
    save(root, DIST_SNAPSHOT, d)
    packet = review(root, pr_root=tmp_path / "pr")
    out = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert out["skipped_duplicate_or_unsafe_company_rows"] == 1
    assert all(x["label"] != "Example Enterprise" for x in out["opportunities"])


def test_duplicate_unbound_company_deduplicated_without_fake_id(tmp_path):
    root, _, _ = _packet(tmp_path)
    p = root / DIST_SNAPSHOT
    d = json.loads(p.read_text())
    d["human_review_queue"].append(dict(d["human_review_queue"][1]))
    save(root, DIST_SNAPSHOT, d)
    packet = review(root, pr_root=tmp_path / "pr")
    out = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert out["skipped_duplicate_or_unsafe_company_rows"] == 1
    assert out["counts"]["unbound_researched_account"] == 1


def test_founder_review_api_composes_the_new_leadgen_queue(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.founder_earned_media_api import create_founder_earned_media_router
    root, pr, _ = _packet(tmp_path)
    app = FastAPI()
    app.include_router(create_founder_earned_media_router(
        enabled=True, repo_root=root, pr_root=pr, distribution_root=root,
    ))
    response = TestClient(app).get("/v1/founder-earned-media/review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["lead_generation"]["counts"]["total"] == 5
    assert payload["lead_generation"]["qualified_buyers_verified"] == 0
    assert payload["lead_generation"]["crm_writes"] is False
    assert payload["lead_generation"]["outbound_authorized"] is False
    assert payload["lead_generation"]["conditional_unit_economics_examples"][0][
        "not_a_forecast"] is True


def test_revenue_experiment_never_treated_as_booked_cash(tmp_path):
    root, _, packet = _packet(tmp_path)
    result = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert len(result["conditional_unit_economics_examples"]) == 3
    assert result["conditional_unit_economics_examples"][0][
        "gross_contract_amount_gbp_minor_if_all_conditions_met"] == 1000000
    assert result["expected_revenue_gbp_minor"] is None
    assert result["realised_revenue_gbp_minor"] is None
    assert result["conversion_probability"] is None
    assert result["acquisition_conversion_contract"][-1]["verified_here"] is False
