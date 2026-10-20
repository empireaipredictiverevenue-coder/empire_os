"""Offline prepublication risk checks. No public site or customer mutation."""
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import json
import pytest

from empire_os.campaign_intelligence import (
    AccountIntelligenceContext, TrustedBuyerValueProblem,
    TrustedOfferCapability, TrustedBuyerValueCase,
    build_private_buyer_offer_experience,
)
from empire_os.commercial_product_catalog import summarize_catalog
from empire_os.owned_campaign_content import PRIVACY
from scripts.review_tam_full_funnel_strategy_20261020 import (
    review_commercial_catalog_for_conversion,
    review_proposed_proof_placement,
    review_hypothetical_market_placement_risks,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAMPAIGN = "campaign_" + "a"*24
GB = "GB:solar:buyers"
US = "US:roofing:buyers"
APPROVALS = {
    "source_proof_claims_approval": True,
    "website_publication_approval": True,
    "privacy_form_approval": True,
    "fulfilment_and_delivery_approval": True,
}


def source():
    row = {
        "product_code": "managed_service",
        "active": True, "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "price_basis": {"state": "VERIFIED", "amount_cents": 2000,
                        "currency": "USD", "unit": "one_time"},
        "acquisition_cost_basis": {"state": "VERIFIED"},
        "fulfilment_cost_basis": {"state": "VERIFIED"},
        "margin_policy": {"state": "VERIFIED"},
    }
    data = summarize_catalog([row])
    data["generated_at"] = NOW.isoformat()
    return data


def release(*, niche="roofing", geo="denver, co",
            objective="research_enquiry", product=None):
    return {"campaigns": [{
        "campaign_id": CAMPAIGN,
        "niche": niche, "geography": geo,
        "campaign_objective": objective,
        "product_code": product,
        "conversion_plan": {"landing_path": "/research/" + CAMPAIGN},
        "assets": [{
            "asset_type": "landing_page",
            "asset_id": CAMPAIGN + ":landing",
            "privacy_notice": PRIVACY,
        }],
        "outbound_authorized": False,
        "automatic_followup": False,
    }]}


def value_case(scope=US, cid=CAMPAIGN):
    ctx = AccountIntelligenceContext(
        tenant_ref="tenant_empireai", account_key="a"*32,
        market_scope=scope, campaign_id=cid,
        canonical_account_verified=True, suppression_clear=True,
        inbound_response_basis_verified=True,
        marketing_contact_basis_verified=False,
        offer_evidence_current=True,
    )
    prob = TrustedBuyerValueProblem(
        tenant_ref=ctx.tenant_ref, account_key=ctx.account_key,
        market_scope=scope, problem_code="supply_territory_fit",
        observed_at=NOW, buyer_directly_stated_problem=True,
        canonical_crm_evidence_verified=True,
    )
    cap = TrustedOfferCapability(
        tenant_ref=ctx.tenant_ref, market_scope=scope,
        offer_arm="buyer_inventory_fit_offer",
        capability_source="canonical_inventory",
        proof_kind="verified_supply_acceptance_fit",
        proof_key="e"*32, verified_at=NOW,
        source_receipt_verified=True, currently_deliverable=True,
        verified_sufficient_market_fit=True,
    )
    return TrustedBuyerValueCase(
        context=ctx, problem=prob, capabilities=(cap,),
    )


def preview(monkeypatch, *, scope=US, signed=None, case=None,
            content=None, approval=None, product=None,
            objective="research_enquiry", auto=False, paid=False,
            territory="denver, co", territory_verified=True):
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: signed if signed is not None else release(),
    )
    c = case or value_case(scope)
    page = content if content is not None else build_private_buyer_offer_experience(
        c, verified_signals=(), now=NOW,
    )
    data = source()
    return review_proposed_proof_placement(
        root=Path("/offline-fixture"), requested_campaign_id=CAMPAIGN,
        proposed_market_scope=scope,
        proposed_offer_arm="buyer_inventory_fit_offer",
        intended_conversion_objective=objective,
        catalog_source=data,
        catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
        proof_preview=page, source_value_case=c, source_signals=(),
        now=NOW, proposed_product_code=product,
        proposed_target_geography=territory,
        target_geography_source_verified=territory_verified,
        approvals=APPROVALS if approval is None else approval,
        approval_content_sha256_by_owner={
            key: sha256(page["private_html"].encode("utf-8")).hexdigest()
            if isinstance(page.get("private_html"), str) else "0"*64
            for key in APPROVALS
        },
        marketing_or_auto_followup_requested=auto,
        paid_media_requested=paid,
    )


def test_same_market_review_is_not_publication_authority(monkeypatch):
    result = preview(monkeypatch)
    assert result["status"] == "READY_FOR_INDEPENDENT_WEBSITE_OWNER_PREFLIGHT"
    assert result["blocking_issue_count"] == 0
    assert result["publication_authorized"] is False
    assert result["outbound_authorized"] is False
    assert result["website_release_writer_enforcement_installed"] is False


def test_uk_solar_to_us_roofing_rejected_before_release(monkeypatch):
    result = preview(monkeypatch, scope=GB)
    assert result["status"] == "CRITICAL_PREPUBLICATION_HOLD"
    assert "COUNTRY_SCOPE_MISMATCH" in result["risk_codes"]
    assert "SECTOR_SCOPE_MISMATCH" in result["risk_codes"]
    assert result["destination_country_and_sector_match_verified"] is False


def test_wrong_industry_only_rejected(monkeypatch):
    result = preview(monkeypatch, signed=release(
        niche="class action lawyer", geo="atlanta",
    ))
    assert "SECTOR_SCOPE_MISMATCH" in result["risk_codes"]
    assert "COUNTRY_SCOPE_MISMATCH" not in result["risk_codes"]


def test_unknown_source_market_held(monkeypatch):
    result = preview(monkeypatch, signed=release(geo="unknown-place"))
    assert "UNKNOWN_SOURCE_MARKET" in result["risk_codes"]


def test_product_cta_cannot_be_added_to_research_only_campaign(monkeypatch):
    result = preview(monkeypatch, objective="product_enquiry",
                     product="managed_service")
    assert "CONVERSION_OBJECTIVE_MISMATCH" in result["risk_codes"]
    result = preview(monkeypatch, product="managed_service")
    assert "RESEARCH_FORM_IS_NOT_PRODUCT_CHECKOUT" in result["risk_codes"]


def test_exact_product_enquiry_with_catalog_is_only_candidate_for_owner_check(monkeypatch):
    result = preview(monkeypatch, objective="product_enquiry",
                     product="managed_service",
                     signed=release(objective="product_enquiry",
                                    product="managed_service"))
    assert result["blocking_issue_count"] == 0
    assert result["publication_authorized"] is False


def test_forged_product_code_does_not_inherit_verified_terms(monkeypatch):
    result = preview(monkeypatch, objective="product_enquiry",
                     product="another_product",
                     signed=release(objective="product_enquiry",
                                    product="managed_service"))
    assert "PRODUCT_CODE_MISMATCH" in result["risk_codes"]
    assert "PRODUCT_TERMS_UNVERIFIED" in result["risk_codes"]


def test_missing_approval_holds_even_with_valid_country_and_product(monkeypatch):
    result = preview(monkeypatch, approval={
        name: False for name in APPROVALS
    })
    assert "UNVERIFIED_PROOF_CLAIMS_APPROVAL" in result["risk_codes"]
    assert "UNVERIFIED_WEBSITE_APPROVAL" in result["risk_codes"]
    assert "UNVERIFIED_PRIVACY_REVIEW" in result["risk_codes"]
    assert "UNVERIFIED_FULFILMENT_APPROVAL" in result["risk_codes"]
    assert all(risk["severity"] == "critical" for risk in result["risks"])


def test_approval_data_must_be_complete_and_strictly_boolean(monkeypatch):
    with pytest.raises(ValueError, match="EXACT_TYPED_OWNER_APPROVAL"):
        preview(monkeypatch, approval={"website_publication_approval": True})
    with pytest.raises(ValueError, match="EXACT_TYPED_OWNER_APPROVAL"):
        preview(monkeypatch, approval={
            **APPROVALS, "website_publication_approval": "true",
        })


def test_content_changed_after_source_review_cannot_pass(monkeypatch):
    c = value_case()
    page = build_private_buyer_offer_experience(c, verified_signals=(), now=NOW)
    changed = {
        **page,
        "private_html": page["private_html"] + " Unverified performance advantage.",
    }
    result = preview(monkeypatch, case=c, content=changed)
    assert "PROOF_CONTENT_NOT_SOURCE_BOUND" in result["risk_codes"]


def test_source_case_bound_to_different_campaign_cannot_be_reused(monkeypatch):
    c = value_case(cid="campaign_" + "f"*24)
    result = preview(monkeypatch, case=c)
    assert "PROOF_CONTENT_NOT_SOURCE_BOUND" in result["risk_codes"]


def test_unknown_website_release_and_auto_spend_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: None,
    )
    data = source()
    result = review_proposed_proof_placement(
        root=Path("/offline-fixture"),
        requested_campaign_id=CAMPAIGN,
        proposed_market_scope=US,
        proposed_offer_arm="buyer_inventory_fit_offer",
        intended_conversion_objective="research_enquiry",
        catalog_source=data,
        catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
        marketing_or_auto_followup_requested=True,
        paid_media_requested=True,
    )
    assert "NO_SIGNED_DESTINATION_RELEASE" in result["risk_codes"]
    assert "PAID_MEDIA_OR_AUTOMATED_OUTBOUND_NOT_AUTHORIZED" in result["risk_codes"]
    assert "UNVERIFIED_SALES_CHANNEL_BASIS" in result["risk_codes"]


def test_existing_approval_does_not_enable_paid_outreach(monkeypatch):
    result = preview(monkeypatch, auto=True, paid=True)
    assert "PAID_MEDIA_OR_AUTOMATED_OUTBOUND_NOT_AUTHORIZED" in result["risk_codes"]
    assert "UNVERIFIED_SALES_CHANNEL_BASIS" in result["risk_codes"]
    assert result["publication_authorized"] is False


@pytest.mark.parametrize("column,value", [
    ("proposed_market_scope", ["GB:solar:buyers"]),
    ("proposed_market_scope", "GB:roofing:buyers"),
    ("proposed_offer_arm", "guaranteed_revenue"),
    ("intended_conversion_objective", "instant_checkout"),
    ("requested_campaign_id", "untrusted"),
    ("marketing_or_auto_followup_requested", "false"),
    ("paid_media_requested", 1),
])
def test_invalid_market_or_execution_request_rejected(monkeypatch, column, value):
    data = source()
    params = dict(
        root=Path("/offline-fixture"), requested_campaign_id=CAMPAIGN,
        proposed_market_scope=US,
        proposed_offer_arm="buyer_inventory_fit_offer",
        intended_conversion_objective="research_enquiry",
        catalog_source=data,
        catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
    )
    params[column] = value
    with pytest.raises(ValueError, match="UNTRUSTED_OR_UNSUPPORTED"):
        review_proposed_proof_placement(**params)


def test_approval_digests_bound_to_exact_page_version(monkeypatch):
    c = value_case()
    page = build_private_buyer_offer_experience(c, verified_signals=(), now=NOW)
    data = source()
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: release(),
    )
    params = dict(
        root=Path("/offline-fixture"),
        requested_campaign_id=CAMPAIGN,
        proposed_market_scope=US,
        proposed_offer_arm="buyer_inventory_fit_offer",
        intended_conversion_objective="research_enquiry",
        catalog_source=data,
        catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
        proof_preview=page,
        source_value_case=c,
        source_signals=(),
        now=NOW,
        proposed_target_geography="denver, co",
        target_geography_source_verified=True,
        approvals=APPROVALS,
    )
    without_digest = review_proposed_proof_placement(**params)
    assert "STALE_OR_MISSING_EXACT_CONTENT_SIGNOFF" in without_digest["risk_codes"]
    good = sha256(page["private_html"].encode("utf-8")).hexdigest()
    old = sha256(b"old approved copy").hexdigest()
    stale_one = review_proposed_proof_placement(
        **params,
        approval_content_sha256_by_owner={
            **{key: good for key in APPROVALS},
            "privacy_form_approval": old,
        },
    )
    assert "STALE_OR_MISSING_EXACT_CONTENT_SIGNOFF" in stale_one["risk_codes"]
    correct = review_proposed_proof_placement(
        **params,
        approval_content_sha256_by_owner={
            key: good for key in APPROVALS
        },
    )
    assert "STALE_OR_MISSING_EXACT_CONTENT_SIGNOFF" not in correct["risk_codes"]
    assert correct["publication_authorized"] is False


def test_invalid_owner_approval_content_digest_is_rejected():
    data = source()
    with pytest.raises(ValueError, match="EXACT_SHA256_OWNER_APPROVAL"):
        review_proposed_proof_placement(
            root=Path("/offline-fixture"), requested_campaign_id=CAMPAIGN,
            proposed_market_scope=US,
            proposed_offer_arm="buyer_inventory_fit_offer",
            intended_conversion_objective="research_enquiry",
            catalog_source=data,
            catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
            approval_content_sha256_by_owner={
                key: "signed" for key in APPROVALS
            },
        )


def test_hypothetical_risk_audit_shows_conflicts_without_contact_data(monkeypatch):
    first = release()["campaigns"][0]
    second = {
        **first,
        "campaign_id": "campaign_"+"b"*24,
        "conversion_plan": {
            "landing_path": "/research/campaign_"+"b"*24,
        },
        "geography": "atlanta", "niche": "class action lawyer",
    }
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: {"campaigns": [first, second]},
    )
    data = source()
    summary = review_hypothetical_market_placement_risks(
        Path("/offline-fixture"),
        market_scope=GB,
        catalog_source=data,
        catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
    )
    assert summary["routes_compared"] == 2
    assert summary["geography_mismatch_routes"] == 2
    assert summary["sector_mismatch_routes"] == 2
    assert summary["actual_proposed_placements_checked"] == 0
    assert summary["actual_queued_publications_detected"] is False
    assert summary["website_release_writer_enforcement_installed"] is False
    assert summary["publication_authorized"] is False
    assert CAMPAIGN not in json.dumps(summary)


def test_old_commercial_catalog_cannot_pass_even_if_caller_replays_ready_label(monkeypatch):
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: release(),
    )
    data = source()
    claims_readiness = review_commercial_catalog_for_conversion(data, now=NOW)
    data["generated_at"] = "2026-10-01T12:00:00+00:00"
    result = review_proposed_proof_placement(
        root=Path("/offline-fixture"),
        requested_campaign_id=CAMPAIGN,
        proposed_market_scope=US,
        proposed_offer_arm="buyer_inventory_fit_offer",
        intended_conversion_objective="research_enquiry",
        catalog_source=data,
        catalog_readiness=claims_readiness,
        now=NOW,
    )
    assert "CATALOG_TERMS_NOT_CURRENT" in result["risk_codes"]
    assert result["publication_authorized"] is False


def test_owner_board_discloses_that_live_publisher_enforcement_is_not_installed():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        export_conversion_owner_handoff,
    )
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_conversion_owner_release_board,
    )
    catalog_source = source()
    readiness = review_commercial_catalog_for_conversion(catalog_source, now=NOW)
    research = {
        "source_status": "AWAIT_AUTHORIZED_DATABASE_OPERATOR",
        "accepted_research_enquiries": None,
    }
    released = {
        "release_status": "EXISTING_RELEASED_RESEARCH_PATHS_VERIFIED",
        "verified_research_pages": 5,
        "existing_enquiry_route": "/api/research/enquiry",
    }
    content = {
        "existing_first_party_research_release": released,
        "existing_catalog_conversion_readiness": readiness,
        "research_enquiry_aggregate_conversion_readiness": research,
        "conversion_release_owner_board": review_conversion_owner_release_board(
            release=released, catalog=readiness, research_aggregate=research,
            customer_money_join=None,
        ),
        "decision_intelligence": {"real_first_party_conversion_journey": None},
    }
    report = export_conversion_owner_handoff(content, now=NOW)
    website = report["website"]
    assert website["prepublication_proof_risk_api_implemented_in_feature_branch"] is True
    assert website["prepublication_proof_risk_enforced_in_live_release_writer"] is False
    assert website["actual_new_publication_queue_authenticated_here"] is False


def test_us_roofing_evidence_from_wrong_metro_is_critical_even_if_country_and_sector_match(monkeypatch):
    result = preview(monkeypatch, territory="atlanta")
    assert result["status"] == "CRITICAL_PREPUBLICATION_HOLD"
    assert "COUNTRY_SCOPE_MISMATCH" not in result["risk_codes"]
    assert "SECTOR_SCOPE_MISMATCH" not in result["risk_codes"]
    assert "TERRITORY_SCOPE_MISMATCH" in result["risk_codes"]
    assert result["destination_territory_match_verified"] is False
    assert result["publication_authorized"] is False


def test_same_metro_without_verified_territory_provenance_holds(monkeypatch):
    result = preview(monkeypatch, territory_verified=False)
    assert "TERRITORY_SCOPE_UNVERIFIED" in result["risk_codes"]
    assert result["destination_territory_match_verified"] is False
    assert result["publication_authorized"] is False
    result = preview(monkeypatch, territory=None)
    assert "TERRITORY_SCOPE_UNVERIFIED" in result["risk_codes"]


def test_exact_metro_with_verified_evidence_is_eligible_only_for_owner_preflight(monkeypatch):
    result = preview(monkeypatch)
    assert result["destination_territory_match_verified"] is True
    assert result["destination_first_party_landing_privacy_verified"] is True
    assert result["blocking_issue_count"] == 0
    assert result["publication_authorized"] is False


@pytest.mark.parametrize("changed_asset", [
    {"asset_type": "landing_page",
     "asset_id": "campaign_"+"f"*24+":landing",
     "privacy_notice": PRIVACY},
    {"asset_type": "landing_page",
     "asset_id": CAMPAIGN+":landing",
     "privacy_notice": "Submitting the form signs you up to marketing."},
    {"asset_type": "landing_page",
     "asset_id": CAMPAIGN+":landing"},
    {"asset_type": "paid_checkout",
     "asset_id": CAMPAIGN+":landing",
     "privacy_notice": PRIVACY},
])
def test_replaced_landing_asset_or_privacy_text_blocks_publication(monkeypatch, changed_asset):
    campaign = release()["campaigns"][0]
    campaign["assets"] = [changed_asset]
    result = preview(monkeypatch, signed={"campaigns": [campaign]})
    assert "RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH" in result["risk_codes"]
    assert result["destination_first_party_landing_privacy_verified"] is False


def test_ambiguous_landing_asset_collection_blocks_publication(monkeypatch):
    campaign = release()["campaigns"][0]
    campaign["assets"].append(dict(campaign["assets"][0]))
    result = preview(monkeypatch, signed={"campaigns": [campaign]})
    assert "RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH" in result["risk_codes"]


@pytest.mark.parametrize("flag,value", [
    ("outbound_authorized", True),
    ("automatic_followup", True),
    ("automatic_followup", "False"),
])
def test_modified_campaign_followup_authority_fails_closed(monkeypatch, flag, value):
    campaign = release()["campaigns"][0]
    campaign[flag] = value
    result = preview(monkeypatch, signed={"campaigns": [campaign]})
    assert "RESEARCH_RELEASE_OUTBOUND_POLICY_CHANGED" in result["risk_codes"]
    assert result["destination_first_party_landing_privacy_verified"] is False
    assert result["outbound_authorized"] is False


@pytest.mark.parametrize("field,value", [
    ("proposed_target_geography", ["denver, co"]),
    ("proposed_target_geography", "a"*121),
    ("target_geography_source_verified", "true"),
])
def test_untrusted_territory_provenance_input_is_not_accepted(field, value):
    data = source()
    args = dict(
        root=Path("/offline-fixture"),
        requested_campaign_id=CAMPAIGN,
        proposed_market_scope=US,
        proposed_offer_arm="buyer_inventory_fit_offer",
        intended_conversion_objective="research_enquiry",
        catalog_source=data,
        catalog_readiness=review_commercial_catalog_for_conversion(data, now=NOW),
        now=NOW,
    )
    args[field] = value
    with pytest.raises(ValueError, match="UNTRUSTED_OR_UNSUPPORTED"):
        review_proposed_proof_placement(**args)


def _final_signoff(html):
    return {name: sha256(html).hexdigest() for name in APPROVALS}


def _final_owner_release_packet(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        require_proof_placement_at_owner_release_boundary,
    )
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: release(),
    )
    c = value_case()
    page = build_private_buyer_offer_experience(c, verified_signals=(), now=NOW)
    catalog = source()
    exact_digest = sha256(page["private_html"].encode("utf-8")).hexdigest()
    placement = {
        "root": Path("/offline-fixture"),
        "requested_campaign_id": CAMPAIGN,
        "proposed_market_scope": US,
        "proposed_offer_arm": "buyer_inventory_fit_offer",
        "intended_conversion_objective": "research_enquiry",
        "catalog_source": catalog,
        "catalog_readiness": review_commercial_catalog_for_conversion(
            catalog, now=NOW,
        ),
        "proof_preview": page,
        "source_value_case": c,
        "source_signals": (),
        "now": NOW,
        "proposed_target_geography": "denver, co",
        "target_geography_source_verified": True,
        "approvals": APPROVALS,
        "approval_content_sha256_by_owner": {
            name: exact_digest for name in APPROVALS
        },
    }
    return (
        page["private_html"].encode("utf-8"), placement,
        require_proof_placement_at_owner_release_boundary,
    )


def test_owner_release_boundary_check_passes_exact_bytes_to_separate_site_review(monkeypatch):
    html, placement, check = _final_owner_release_packet(monkeypatch)
    result = check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert result["status"] == "READY_FOR_INDEPENDENT_WEBSITE_OWNER_RELEASE_CHECKS"
    assert result["candidate_html_sha256"] == sha256(html).hexdigest()
    assert result["risk_issue_count"] == 0
    assert result["source_owner_attestations_independently_authenticated_here"] is False
    assert result["publication_authorized"] is False
    assert result["published"] is False
    assert result["release_writer_hook_installed"] is False


@pytest.mark.parametrize("variation", [
    lambda b: b + b" Extra unsupported guarantee.",
    lambda b: b.replace(b"PRIVATE PREVIEW", b"PUBLIC RELEASE"),
    lambda b: b"not the expected page",
    lambda b: b"",
])
def test_owner_release_boundary_blocks_asset_mutation_after_signoff(
    monkeypatch, variation,
):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=variation(html),
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert caught.value.reason_codes
    assert any(x in caught.value.reason_codes for x in (
        "FINAL_ASSET_CHANGED_AFTER_OWNER_SIGNOFF",
        "FINAL_RENDERED_ASSET_SIZE_INVALID",
    ))


def test_owner_release_boundary_blocks_wrong_city_even_if_final_bytes_valid(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    placement["proposed_target_geography"] = "atlanta"
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert "TERRITORY_SCOPE_MISMATCH" in caught.value.reason_codes


def test_owner_release_boundary_blocks_privacy_change_without_inventing_permission(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    campaign = release()["campaigns"][0]
    campaign["assets"][0]["privacy_notice"] = "marketing subscription"
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: {"campaigns": [campaign]},
    )
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert "RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH" in caught.value.reason_codes


@pytest.mark.parametrize("bad", [
    None, "HTML string not bytes", 1, [], {"raw": "html"},
])
def test_owner_release_boundary_refuses_untyped_written_artifact(monkeypatch, bad):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html_fixture, placement, check = _final_owner_release_packet(monkeypatch)
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=bad,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html_fixture),
        )
    assert "FINAL_RENDERED_ASSET_NOT_BYTES" in caught.value.reason_codes


def test_owner_release_boundary_missing_approval_digest_or_source_holds(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    placement["approval_content_sha256_by_owner"] = None
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert "STALE_OR_MISSING_EXACT_CONTENT_SIGNOFF" in caught.value.reason_codes
    _, placement, check = _final_owner_release_packet(monkeypatch)
    placement["source_value_case"] = None
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert "PROOF_CONTENT_NOT_SOURCE_BOUND" in caught.value.reason_codes


def test_owner_release_boundary_rejects_unexpected_argument_or_missing_contract(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    placement["allow_unverified_publish"] = True
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert "EXACT_RELEASE_PLACEMENT_ARGUMENTS_REQUIRED" in caught.value.reason_codes
    placement.pop("allow_unverified_publish")
    placement.pop("now")
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=_final_signoff(html),
        )
    assert "EXACT_RELEASE_PLACEMENT_ARGUMENTS_REQUIRED" in caught.value.reason_codes


def test_public_page_with_separately_approved_form_can_pass_final_byte_review(monkeypatch):
    # The approved PRIVATE proof is input evidence, NOT the final public HTML.
    # A site owner may add a compliant rendered first-party form/CTA under
    # independent claims, privacy, website and fulfilment approvals.
    html, placement, check = _final_owner_release_packet(monkeypatch)
    public_html = html.replace(
        b"PRIVATE PREVIEW",
        b"WEBSITE OWNER APPROVED PUBLIC BRIEF",
    ).replace(
        b"</main></body>",
        b'<form method="post" action="/api/research/enquiry">'
        b'<input name="campaign_id" value="fixture" />'
        b'<button>Request research</button></form></main></body>',
    )
    assert public_html != html
    result = check(
        candidate_html_bytes=public_html,
        placement_arguments=placement,
        final_artifact_signoff_sha256_by_owner=_final_signoff(public_html),
    )
    assert result["candidate_html_sha256"] == sha256(public_html).hexdigest()
    assert result["final_artifact_digest_matches_all_owner_claims"] is True
    assert result["exact_publication_route_authenticated_here"] is False
    assert result["first_party_form_or_privacy_deployment_verified_here"] is False
    assert result["publication_authorized"] is False


def test_public_page_even_one_byte_modified_after_final_owner_signoff_is_blocked(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    public_html = html.replace(b"PRIVATE PREVIEW", b"PUBLIC REVIEWED BRIEF")
    owners = _final_signoff(public_html)
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=public_html+b" ",
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=owners,
        )
    assert "FINAL_ASSET_CHANGED_AFTER_OWNER_SIGNOFF" in caught.value.reason_codes


@pytest.mark.parametrize("bad_signoffs", [
    None,
    {},
    {"website_publication_approval": "f"*64},
    {name: "NOT_A_REAL_DIGEST" for name in APPROVALS},
])
def test_no_final_public_artifact_can_pass_without_all_owner_digest_claims(
    monkeypatch, bad_signoffs,
):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        ProofPrepublicationHeld,
    )
    html, placement, check = _final_owner_release_packet(monkeypatch)
    with pytest.raises(ProofPrepublicationHeld) as caught:
        check(
            candidate_html_bytes=html,
            placement_arguments=placement,
            final_artifact_signoff_sha256_by_owner=bad_signoffs,
        )
    assert "FINAL_ARTIFACT_OWNER_SIGNOFFS_REQUIRED" in caught.value.reason_codes
