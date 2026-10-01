from copy import deepcopy
import hashlib
from empire_os.owned_campaign_content import PRIVACY, render_asset

import pytest
from starlette.routing import Match

from empire_os.owned_campaign_preflight import (
    EVENT_FIELDS, INFRASTRUCTURE_GATES, digest, inspect_campaigns, lookup_campaign,
)
from empire_os.public_gateway import app, _sitemap_xml, _site_html_path


def campaign(number=1):
    cid = f"campaign_{number:024x}"
    return {
        "campaign_id": cid, "current_stage": "READY_FOR_OWNED_ACTIVATION",
        "execution_authority": "none", "account_label": "Empire AI",
        "account_id": None, "tenant_id": None,
        "tenant_scope": {"customer_access_authorized": False},
        "opportunity_key": "test:research", "opportunity_evidence_refs": ["test:evidence"],
        "campaign_objective": "research_enquiry", "product_code": None, "product_id": None,
        "claim_review": {"status": "PASS", "scope": "claim-free research invitation templates"},
        "assets": [{"asset_type": "landing_page", "asset_id": f"{cid}:landing",
                    "campaign_id": cid, "h1": "Research", "thesis": "Questions",
                    "claims": [], "copy": {"claims": []}, "cta": "Enquire about the research",
                    "seo_title": f"Research {number}", "meta_description": f"Evidence review {number}",
                    "privacy_notice": PRIVACY, "internal_links": ["/trust"],
                    "evidence_refs": ["test:evidence"],
                    "sections": [{"heading": "Questions", "body": f"Review sources {number}"}]}],
        "conversion_plan": {"conversion_objective": "email_enquiry",
                            "primary_cta": "Enquire about the research",
                            "landing_path": f"/research/{cid}"},
        "attribution_plan": {"campaign_id": cid, "asset_ids": [f"{cid}:landing"],
                             "event_contract": {"required": sorted(EVENT_FIELDS)},
                             "source": "owned_site", "medium": "organic"},
        "predictive_revenue_status": "UNAVAILABLE",
        "paid_media_spend_cents": 0,
    }


def reviewed(c):
    c["owned_publication_review"] = {
        "status": "PASS", "asset_sha256": hashlib.sha256(render_asset(c["assets"][0]).encode()).hexdigest(),
        "asset_contract_sha256": digest(c["assets"][0]),
        "campaign_id": c["campaign_id"], "asset_id": c["assets"][0]["asset_id"],
        "claim_inventory": [], "claim_verification_result": {"status": "PASS"},
        "evidence_refs": ["test:evidence"], "independent_visitor_value": True,
        "limitations_present": True, "privacy_surface_present": True,
    }
    return c


def infrastructure():
    return {key: {"status": "PASS", "evidence_refs": ["test:verified"]}
            for key in INFRASTRUCTURE_GATES}


def test_lookup_fails_closed_and_returns_copy():
    c = campaign()
    m = {"campaigns": [c]}
    lookup_campaign(m, c["campaign_id"])["current_stage"] = "ACTIVE"
    assert c["current_stage"] == "READY_FOR_OWNED_ACTIVATION"
    for cid in ("../trust", "campaign_" + "2" * 24, None):
        with pytest.raises(ValueError):
            lookup_campaign(m, cid)
    with pytest.raises(ValueError):
        lookup_campaign({"campaigns": [c, c]}, c["campaign_id"])


def test_independent_gates_idempotence_no_mutation_no_prediction_gate():
    m = {"campaigns": [reviewed(campaign()), campaign(2)]}
    original = deepcopy(m)
    result = inspect_campaigns(m, infrastructure())
    assert result == inspect_campaigns(m, infrastructure())
    assert m == original
    assert result["campaigns_preflight_passed"] == 1
    assert result["campaigns_blocked"] == 1
    assert not result["campaign_state_mutated"]
    assert not result["publication_performed"]


@pytest.mark.parametrize("stage", ["ACTIVE", "MEASURING", "DRAFT", None])
def test_unrelated_or_already_active_campaign_not_promoted(stage):
    c = reviewed(campaign())
    c["current_stage"] = stage
    result = inspect_campaigns({"campaigns": [c]}, infrastructure())
    assert "ready_stage" in result["campaigns"][0]["blockers"]
    assert c["current_stage"] == stage


def test_unknown_product_cannot_be_commercial():
    c = campaign()
    c["assets"][0]["cta"] = "Discuss product fit"
    result = inspect_campaigns({"campaigns": [c]}, {})
    assert "product_and_cta" in result["campaigns"][0]["blockers"]


def test_managed_service_cta_and_no_invented_tenant():
    c = campaign()
    c.update(product_code="managed_service", product_id="test:product",
             product_evidence_refs=["test:catalog"])
    c["assets"][0]["cta"] = c["conversion_plan"]["primary_cta"] = "Discuss product fit"
    result = inspect_campaigns({"campaigns": [c]}, {})["campaigns"][0]
    assert result["gates"]["product_and_cta"]
    assert result["account_id"] is None and result["tenant_id"] is None


def test_claim_and_content_review_bound_to_asset():
    c = reviewed(campaign())
    c["assets"][0]["claims"] = ["Guaranteed results"]
    result = inspect_campaigns({"campaigns": [c]}, infrastructure())["campaigns"][0]
    assert "useful_content_review" in result["blockers"]
    assert "useful_content_review" in result["blockers"]


def test_infrastructure_unknown_and_session_never_establish_identity():
    c = campaign()
    c["session_id"] = "test:session"
    c["utm_campaign"] = c["campaign_id"]
    result = inspect_campaigns({"campaigns": [c]}, {})
    assert set(INFRASTRUCTURE_GATES).issubset(result["campaigns"][0]["blockers"])
    assert "prospect_id" not in result["campaigns"][0]
    assert "marketing_consent" not in result["campaigns"][0]


def test_attribution_requires_matching_evidence_contract():
    c = campaign()
    c["attribution_plan"]["event_contract"]["required"].remove("occurred_at")
    assert not inspect_campaigns({"campaigns": [c]}, {})["campaigns"][0]["gates"]["event_contract"]


@pytest.mark.parametrize("number", range(1, 6))
def test_unpublished_routes_fail_closed_and_not_in_sitemap(tmp_path, number):
    cid = campaign(number)["campaign_id"]
    path = f"/research/{cid}"
    scope = {"type": "http", "method": "GET", "path": path, "root_path": ""}
    from empire_os.public_gateway import research_page
    assert research_page(cid).status_code == 404
    assert _site_html_path(path, tmp_path) is None
    assert cid not in _sitemap_xml(tmp_path, tmp_path)


def test_paid_spend_blocks_even_with_other_reviews():
    c = reviewed(campaign())
    c["paid_media_spend_cents"] = 1
    assert "zero_paid_spend" in inspect_campaigns(
        {"campaigns": [c]}, infrastructure())["campaigns"][0]["blockers"]
