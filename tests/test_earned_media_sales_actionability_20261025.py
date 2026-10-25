"""Fresh public search indexing is not buying intent, access or credentials."""
import copy
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.earned_media_advisory_bridge import review
from empire_os.earned_media_leadgen_review import review_lead_generation
from empire_os.earned_media_sales_actionability import (
    PUBLIC_PROBE_DOC, REQUESTS, review_sales_actionability, review_sales_from_source_file,
)
from empire_os.founder_earned_media_api import create_founder_earned_media_router
from tests.test_earned_media_leadgen_review_20261025 import _packet, save


AT = datetime(2026, 10, 25, 20, tzinfo=timezone.utc)


def _obs():
    return {
        "schema_version": "empire.earned_media.public_request_observation.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "observations": [{
            "source_url": spec["url"],
            "observed_date": "2026-10-25",
            "discovery_channel": "PUBLIC_SEARCH_RESULT",
            "authenticated_listing_available": False,
            "identified_buying_organisation": False,
            "supplier_eligibility_verified": False,
            "outreach_authorized": False,
        } for spec in REQUESTS[:2]],
    }


def _lead(tmp_path):
    root, pr, packet = _packet(tmp_path)
    return root, pr, review_lead_generation(packet, repo_root=root, distribution_root=root)


def test_all_five_held_even_after_public_source_indexing(tmp_path):
    _, _, leadgen = _lead(tmp_path)
    result = review_sales_actionability(leadgen, as_of=AT, public_observations=_obs())
    assert result["total_observations"] == 5
    assert result["actionability_counts"] == {
        "HOLD_MARKETPLACE_ELIGIBILITY_AND_DELIVERY": 2,
        "HOLD_BROKERED_BUYER_ORIGINAL_SOURCE": 1,
        "RESEARCH_ONLY_CANONICAL_ID_NOT_BUYER_INTENT": 1,
        "RESEARCH_ONLY_COMPANY_IDENTITY_UNBOUND": 1,
    }
    assert result["ready_for_contact"] == result["ready_for_proposal"] == 0
    assert result["verified_buyer_conversations"] == result["accepted_clients"] == 0
    assert result["recognised_revenue"] is None
    assert result["source_probe_state"] == "PUBLIC_INDEX_OBSERVATIONS_REVIEWED"
    assert all(not x["eligible_for_outreach"] for x in result["records"])


def test_old_public_search_observations_decay_without_auto_promoting(tmp_path):
    _, _, leadgen = _lead(tmp_path)
    result = review_sales_actionability(
        leadgen, as_of=AT + timedelta(days=4), public_observations=_obs()
    )
    direct = [x for x in result["records"] if
              x["actionability"] == "HOLD_MARKETPLACE_ELIGIBILITY_AND_DELIVERY"]
    assert all(x["source_index_check"] == "STALE_PUBLIC_INDEX_SNAPSHOT" for x in direct)
    assert result["ready_for_contact"] == 0


def test_future_dated_or_claimed_authenticated_public_probe_cannot_grant_sales(tmp_path):
    _, _, leadgen = _lead(tmp_path)
    future = _obs()
    future["observations"][0]["observed_date"] = "2026-10-30"
    response = review_sales_actionability(leadgen, as_of=AT, public_observations=future)
    assert response["source_probe_state"] == "FUTURE_DATED_PUBLIC_PROBE"
    assert response["ready_for_contact"] == 0
    fake = _obs()
    fake["observations"][0]["supplier_eligibility_verified"] = True
    response = review_sales_actionability(leadgen, as_of=AT, public_observations=fake)
    assert response["source_probe_state"] == "INVALID_PUBLIC_PROBE"
    assert not response["records"][0]["eligible_for_outreach"]


def test_duplicate_or_unmatched_probe_is_not_considered_proof(tmp_path):
    _, _, leadgen = _lead(tmp_path)
    fake = _obs()
    fake["observations"].append(copy.deepcopy(fake["observations"][0]))
    result = review_sales_actionability(leadgen, as_of=AT, public_observations=fake)
    assert result["source_probe_state"] == "INVALID_PUBLIC_PROBE"
    assert result["ready_for_proposal"] == 0
    fake = _obs()
    fake["observations"][0]["source_url"] = "https://some-other-domain.invalid"
    result = review_sales_actionability(leadgen, as_of=AT, public_observations=fake)
    assert result["source_probe_state"] == "INVALID_PUBLIC_PROBE"


def test_cannot_misjoin_different_public_source_and_lead_id(tmp_path):
    _, _, leadgen = _lead(tmp_path)
    fake = copy.deepcopy(leadgen)
    fake["opportunities"][0]["source_url"] = REQUESTS[0]["url"]
    assert fake["opportunities"][0]["source_url"] != leadgen["opportunities"][0]["source_url"]
    with pytest.raises(ValueError, match="PUBLIC_REQUEST_SOURCE_MISMATCH"):
        review_sales_actionability(fake, as_of=AT, public_observations=_obs())


def test_disallowed_sender_authority_holds(tmp_path):
    _, _, leadgen = _lead(tmp_path)
    fake = copy.deepcopy(leadgen)
    fake["opportunities"][0]["verified_procurement_intent"] = True
    with pytest.raises(ValueError, match="UNSUPPORTED_CLAIMED_COMMERCIAL_AUTHORITY"):
        review_sales_actionability(fake, as_of=AT)
    fake = copy.deepcopy(leadgen)
    fake["opportunities"].append(copy.deepcopy(fake["opportunities"][0]))
    with pytest.raises(ValueError, match="DUPLICATE_OR_MISSING_LEAD_ID"):
        review_sales_actionability(fake, as_of=AT)


def test_source_adapter_missing_probe_is_held_search_not_buyer(tmp_path):
    root, _, leadgen = _lead(tmp_path)
    output = review_sales_from_source_file(leadgen, repo_root=root, as_of=AT)
    assert output["source_probe_state"] == "NO_PUBLIC_PROBE"
    assert output["observation_source"]["integrity"] == "NO_PROBE_FILE"
    assert output["ready_for_proposal"] == 0
    save(root, PUBLIC_PROBE_DOC, _obs())
    output = review_sales_from_source_file(leadgen, repo_root=root, as_of=AT)
    assert output["source_probe_state"] == "PUBLIC_INDEX_OBSERVATIONS_REVIEWED"
    assert output["observation_source"]["sha256"] is not None
    assert output["ready_for_contact"] == 0


def test_upstream_held_does_not_trigger_probe_read(tmp_path):
    root, _, leadgen = _lead(tmp_path)
    bad = copy.deepcopy(leadgen)
    bad["status"] = "HELD_SOURCE_OR_PACKET_INTEGRITY"
    output = review_sales_from_source_file(bad, repo_root=root, as_of=AT)
    assert output["status"] == "HELD_LEADGEN_UPSTREAM"
    assert output["total_observations"] == 0
    assert output["source_probe_state"] == "NOT_READ_UPSTREAM_HELD"


def test_existing_founder_api_exposes_readiness_without_write_routes(tmp_path):
    root, pr, _ = _lead(tmp_path)
    save(root, PUBLIC_PROBE_DOC, _obs())
    app = FastAPI()
    app.include_router(create_founder_earned_media_router(
        enabled=True, repo_root=root, pr_root=pr, distribution_root=root
    ))
    payload = TestClient(app).get("/v1/founder-earned-media/review").json()
    assert payload["sales_actionability"]["ready_for_contact"] == 0
    assert payload["sales_actionability"]["ready_for_proposal"] == 0
    assert payload["sales_actionability"]["total_observations"] == 5
    for path, ops in app.openapi()["paths"].items():
        assert set(ops) == {"get"}
