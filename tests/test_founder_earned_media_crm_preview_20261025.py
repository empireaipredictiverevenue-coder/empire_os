"""Disabled-by-default Founder route and exact-only CRM review regressions."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.earned_media_crm_match_preview import preview_crm_links
from empire_os.founder_earned_media_api import create_founder_earned_media_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service
from tests.test_earned_media_advisory_bridge_20261025 import prepared
from empire_os.earned_media_advisory_bridge import review


TENANT = "bca9ff8e-7f5a-42eb-a861-a4b5819b2fe0"
COMPANY = "e6bc712f-f0d2-4fcb-8ba5-a0b65faf98c7"
PROSPECT = "6cc80e14-b15c-4623-b71b-563de1d87382"
OPPORTUNITY = "20556f96-be82-495d-b2c1-042102706cdf"


def _client(*, enabled=False, root=None, pr=None):
    app = FastAPI()
    app.include_router(create_founder_earned_media_router(
        enabled=enabled, repo_root=root, pr_root=pr, distribution_root=root,
    ))
    return TestClient(app)


def test_founder_route_disabled_default(monkeypatch):
    monkeypatch.delenv("EMPIRE_EARNED_MEDIA_FOUNDER_READ_ENABLED", raising=False)
    client = _client()
    response = client.get("/v1/founder-earned-media/review")
    assert response.status_code == 404
    assert response.json() == {"detail": "not_enabled"}


def test_founder_service_mounts_existing_loopback_only_read_route():
    paths = build_founder_dashboard_service().openapi()["paths"]
    assert "/v1/founder-earned-media/review" in paths
    methods = paths["/v1/founder-earned-media/review"]
    assert "get" in methods
    assert "post" not in methods
    assert "delete" not in methods


def test_founder_route_returns_read_only_packet_on_injected_sources(tmp_path):
    root, pr = prepared(tmp_path)
    result = _client(enabled=True, root=root, pr=pr).get(
        "/v1/founder-earned-media/review"
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["lane_counts"]["pr"] == 3
    assert payload["read_only"] is True
    assert payload["crm_reconciliation_state"].startswith("NOT_STARTED")
    assert payload["deployment_authorized"] is False
    assert payload["smart_crm_writes"] is False
    assert payload["new_outbound_authorized"] is False


def test_founder_route_holds_absent_source(tmp_path):
    result = _client(enabled=True, root=tmp_path, pr=tmp_path).get(
        "/v1/founder-earned-media/review"
    )
    assert result.status_code == 200
    assert result.json()["status"] == "REVIEW_CONNECTED_WITH_SOURCE_GAPS"
    assert result.json()["items"] == []


def test_preview_fails_closed_if_no_authenticated_tenant(tmp_path):
    root, pr = prepared(tmp_path)
    packet = review(root, pr_root=pr)
    data = preview_crm_links(packet, [], authenticated_tenant_id=None)
    assert data["status"] == "HELD_TENANT_AUTHORITY_UNAVAILABLE"
    assert all(x["match_state"] == "HOLD_AUTHENTICATED_TENANT_ID_MISSING"
               for x in data["items"])
    assert not data["crm_writes_performed"]


def test_preview_only_matches_exact_verified_thread_and_tenant(tmp_path):
    root, pr = prepared(tmp_path)
    packet = review(root, pr_root=pr)
    candidate = {
        "evidence_type": "confirmed_conversation_join_v1",
        "source_provider_thread": "abc123",
        "tenant_id": TENANT,
        "tenant_membership_verified": True,
        "company_identity_verified": True,
        "provider_thread_reconciled": True,
        "canonical_company_id": COMPANY,
        "canonical_prospect_id": PROSPECT,
        "canonical_opportunity_id": OPPORTUNITY,
    }
    outcome = preview_crm_links(packet, [candidate], authenticated_tenant_id=TENANT)
    matches = [x for x in outcome["items"]
               if x["match_state"] == "MATCH_CANDIDATE_OWNER_REVIEW_REQUIRED"]
    assert len(matches) == 1
    assert matches[0]["lane"] == "pr"
    assert matches[0]["canonical_join_candidate_count"] == 1
    assert not matches[0]["automatic_binding_authorized"]
    assert all("canonical_opportunity_id" not in x for x in outcome["items"])

    wrong_tenant = preview_crm_links(
        packet, [candidate], authenticated_tenant_id="97caf3f7-2971-4431-a4cc-5a4ca5174b4b")
    assert not any(x["match_state"] == "MATCH_CANDIDATE_OWNER_REVIEW_REQUIRED"
                   for x in wrong_tenant["items"])

    incomplete = dict(candidate, company_identity_verified=False)
    missing = preview_crm_links(
        packet, [incomplete], authenticated_tenant_id=TENANT)
    assert not any(x["match_state"] == "MATCH_CANDIDATE_OWNER_REVIEW_REQUIRED"
                   for x in missing["items"])


def test_ambiguous_exact_thread_blocks_review(tmp_path):
    root, pr = prepared(tmp_path)
    packet = review(root, pr_root=pr)
    candidate = {
        "evidence_type": "confirmed_conversation_join_v1",
        "source_provider_thread": "abc123",
        "tenant_id": TENANT,
        "tenant_membership_verified": True,
        "company_identity_verified": True,
        "provider_thread_reconciled": True,
        "canonical_company_id": COMPANY,
        "canonical_prospect_id": PROSPECT,
        "canonical_opportunity_id": OPPORTUNITY,
    }
    second = dict(candidate, canonical_opportunity_id="d04c492b-f49e-4a4b-aafc-4ecfd45a3317")
    result = preview_crm_links(packet, [candidate, second],
                               authenticated_tenant_id=TENANT)
    matches = [x for x in result["items"] if x["match_state"] ==
               "HOLD_AMBIGUOUS_CANONICAL_MATCH"]
    assert len(matches) == 1
    assert result["automatic_crm_binding_authorized"] is False


def test_over_limit_canonical_joins_hold_instead_of_hiding_conflicts(tmp_path):
    import pytest
    root, pr = prepared(tmp_path)
    packet = review(root, pr_root=pr)
    with pytest.raises(ValueError, match="OVER_LIMIT"):
        preview_crm_links(packet, [{} for _ in range(201)],
                          authenticated_tenant_id=TENANT)


def test_unsent_pr_cannot_match_even_with_thread_injected(tmp_path):
    root, pr = prepared(tmp_path)
    packet = review(root, pr_root=pr)
    unsent = next(x for x in packet["items"] if x["label"] == "UKTN")
    unsent["source_provider_thread"] = "abc123"
    evidence = {
        "evidence_type": "confirmed_conversation_join_v1",
        "source_provider_thread": "abc123",
        "tenant_id": TENANT,
        "tenant_membership_verified": True,
        "company_identity_verified": True,
        "provider_thread_reconciled": True,
        "canonical_company_id": COMPANY,
        "canonical_prospect_id": PROSPECT,
        "canonical_opportunity_id": OPPORTUNITY,
    }
    outcome = preview_crm_links(packet, [evidence],
                                authenticated_tenant_id=TENANT)
    chosen = next(x for x in outcome["items"] if x["item_id"] == unsent["item_id"])
    assert chosen["match_state"] == "NO_MATCH_ELIGIBLE_EVIDENCE"
