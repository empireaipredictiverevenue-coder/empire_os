"""Value-first sample previews are original, gated and non-sending."""
import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.earned_media_leadgen_review import REQUESTS, _key, review_lead_generation
from empire_os.earned_media_value_first import preview_value_first_sample
from empire_os.founder_earned_media_api import create_founder_earned_media_router
from tests.test_earned_media_leadgen_review_20261025 import _packet


def _leadgen(tmp_path):
    root, pr, packet = _packet(tmp_path)
    result = review_lead_generation(packet, repo_root=root, distribution_root=root)
    assert result["status"] == "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE"
    return root, pr, result


def _client(root, pr, enabled: bool):
    app = FastAPI()
    app.include_router(create_founder_earned_media_router(
        repo_root=root, pr_root=pr, distribution_root=root, enabled=enabled,
    ))
    return TestClient(app)


@pytest.mark.parametrize("spec", REQUESTS)
def test_original_samples_have_matching_source_and_no_sales_claims(tmp_path, spec):
    _, _, leadgen = _leadgen(tmp_path)
    identifier = _key("public_request", spec["url"])
    packet = preview_value_first_sample(leadgen, opportunity_id=identifier)
    assert len(packet["sections"]) >= 4
    assert packet["lead_id"] == identifier
    assert packet["lead_stage"] == "SOURCE_SIGNAL_ONLY"
    assert packet["message_sent"] is False
    assert packet["crm_write_authorized"] is False
    assert packet["proposal_authorized"] is False
    assert packet["revenue_verified"] is False
    assert "ORIGINAL" in packet["sample_type"]


def test_company_sample_requires_independent_fact_check(tmp_path):
    _, _, leadgen = _leadgen(tmp_path)
    company = next(x for x in leadgen["opportunities"]
                   if x["lead_stage"] == "RESEARCHED_ACCOUNT_UNBOUND")
    packet = preview_value_first_sample(
        leadgen, opportunity_id=company["opportunity_id"]
    )
    assert "hypothesis" in packet["title"].lower()
    assert packet["label"] == "Example Trades"
    assert "not a report" in packet["safe_introduction"]
    assert packet["message_drafted"] is False


def test_unknown_and_duplicate_ids_are_never_resolved(tmp_path):
    _, _, leadgen = _leadgen(tmp_path)
    with pytest.raises(LookupError):
        preview_value_first_sample(leadgen, opportunity_id="leadreview_" + "f"*24)
    duplicate = copy.deepcopy(leadgen)
    duplicate["opportunities"].append(copy.deepcopy(duplicate["opportunities"][0]))
    with pytest.raises(LookupError):
        preview_value_first_sample(duplicate,
                                   opportunity_id=duplicate["opportunities"][0]["opportunity_id"])


def test_changed_review_authority_holds_samples(tmp_path):
    _, _, leadgen = _leadgen(tmp_path)
    untrusted = copy.deepcopy(leadgen)
    untrusted["outbound_authorized"] = True
    with pytest.raises(ValueError, match="UNTRUSTED_LEAD_REVIEW"):
        preview_value_first_sample(
            untrusted, opportunity_id=leadgen["opportunities"][0]["opportunity_id"])
    untrusted = copy.deepcopy(leadgen)
    untrusted["opportunities"][0]["quote_authorized"] = True
    with pytest.raises(ValueError, match="PROSPECT_EVIDENCE_INVALID"):
        preview_value_first_sample(
            untrusted, opportunity_id=leadgen["opportunities"][0]["opportunity_id"])


def test_sample_founder_api_is_read_only_and_disabled_by_default(tmp_path):
    root, pr, leadgen = _leadgen(tmp_path)
    path = "/v1/founder-earned-media/lead-opportunity/" + leadgen["opportunities"][0]["opportunity_id"] + "/sample"
    held = _client(root, pr, enabled=False).get(path)
    assert held.status_code == 404
    assert held.json()["detail"] == "not_enabled"
    ready = _client(root, pr, enabled=True).get(path)
    assert ready.status_code == 200
    assert ready.json()["message_sent"] is False
    assert ready.json()["proposal_authorized"] is False
    missing = _client(root, pr, enabled=True).get(
        "/v1/founder-earned-media/lead-opportunity/leadreview_" + "0"*24 + "/sample")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "sample_not_found"


def test_new_founder_api_has_get_only_no_write_actions():
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    paths = build_founder_dashboard_service().openapi()["paths"]
    path = "/v1/founder-earned-media/lead-opportunity/{opportunity_id}/sample"
    assert set(paths[path]) == {"get"}
