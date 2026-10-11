from empire_os.buyer_pilot_assets import (
    build_lead_smart_pilot_assets,
    validate_asset_text,
)
from empire_os.buyer_supply_policy import lead_smart_observed_policy


SOURCE = "gmail:1a0da7880f69e8c6"


def policy():
    return lead_smart_observed_policy(source_ref=SOURCE)


def test_prohibited_guarantee_is_detected():
    result = validate_asset_text(
        "Guaranteed same-day service",
        prohibited_categories=[
            "guarantees",
            "unsubstantiated_claims",
        ],
    )

    assert result["compliant"] is False
    assert any(
        item["category"] == "guarantees"
        for item in result["violations"]
    )


def test_prohibited_discount_is_detected():
    result = validate_asset_text(
        "Save 20% with our discount",
        prohibited_categories=["discounts"],
    )

    assert result["compliant"] is False


def test_lead_smart_assets_are_generic_and_unbranded():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    assert result["compliance_passed"] is True

    for asset in result["assets"]:
        assert asset["brand"] is None
        assert asset["compliance"]["compliant"] is True


def test_lead_smart_assets_do_not_invent_commercial_terms():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    asset_text = str(result["assets"]).lower()

    assert "$" not in asset_text
    assert "payout" not in asset_text
    assert "daily cap" not in asset_text
    assert "volume" not in asset_text


def test_asset_generation_never_authorizes_execution():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    assert result["mode"] == "REVIEW_ONLY"
    assert result["published"] is False
    assert result["campaign_created"] is False
    assert result["budget_authorized"] is False
    assert result["traffic_authorized"] is False
    assert result["commercial_activation_authorized"] is False
    assert result["buyer_approved"] is False


def test_supply_review_remains_blocked_after_asset_generation():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    review = result["current_supply_review"]

    assert review["pilot_ready"] is False
    assert "sites_reviewed" in review["blockers"]
    assert "landing_pages_reviewed" in review["blockers"]
    assert "ads_reviewed" in review["blockers"]
    assert "traffic_source_buyer_approval" in review["blockers"]


def test_partner_review_previews_are_isolated_without_live_cta():
    from empire_os.buyer_pilot_assets import (
        build_partner_landing_review, render_partner_landing_review_html,
    )
    from empire_os.commercial_relationship_registry import PARTNER_LAUNCH_GATES
    import re

    keys = ("leadbank", "validated", "connexis")
    out = {}
    for key in keys:
        packet = {
            "entity_key": key,
            "lead_smart_route_or_number_inherited": False,
            "traffic_enabled": False,
            "execution_authority": "NONE",
            "partner_tracking_number": None,
            "routing_destination_or_sip_endpoint": None,
            "signed_agreement_evidence": None,
        }
        pilot = {
            "entity_key": key,
            "company": key.capitalize(),
            "technical_review_packet": packet,
            "activation_gates": {gate: False for gate in PARTNER_LAUNCH_GATES},
        }
        review = build_partner_landing_review(pilot)
        html = render_partner_landing_review_html(review)
        assert review["entity_key"] == key
        assert review["tracking_number"] is None
        assert review["buyer_disclosure_approved"] is False
        assert review["call_action_enabled"] is False
        assert review["lead_form_enabled"] is False
        assert review["published"] is False
        assert review["execution_authority"] == "NONE"
        assert 'name="robots" content="noindex,nofollow,noarchive"' in html
        assert "<form" not in html.lower()
        assert "tel:" not in html.lower()
        assert "888" not in html
        assert 'disabled aria-disabled="true"' in html
        assert re.search(r"<script|https?://", html, re.I) is None
        out[key] = html
    assert len(set(out.values())) == 3
    assert "roofing-hero.webp" in out["leadbank"]
    assert "roofing-hero.webp" not in out["connexis"]


def test_partner_review_never_inherits_route_or_authority():
    from empire_os.buyer_pilot_assets import build_partner_landing_review
    from empire_os.commercial_relationship_registry import PARTNER_LAUNCH_GATES
    import pytest

    p = {
        "entity_key": "leadbank",
        "company": "LeadBank",
        "technical_review_packet": {
            "entity_key": "leadbank",
            "lead_smart_route_or_number_inherited": False,
            "traffic_enabled": False,
            "execution_authority": "NONE",
            "partner_tracking_number": None,
            "routing_destination_or_sip_endpoint": None,
            "signed_agreement_evidence": None,
        },
        "activation_gates": {x: False for x in PARTNER_LAUNCH_GATES},
    }
    build_partner_landing_review(p)
    p["technical_review_packet"]["partner_tracking_number"] = "+18883579305"
    with pytest.raises(ValueError, match="preview_tracking_number"):
        build_partner_landing_review(p)
    p["technical_review_packet"]["partner_tracking_number"] = None
    p["activation_gates"]["founder_live_traffic_authorized"] = True
    partial=build_partner_landing_review(p)
    assert partial["approval_gates"]["founder_live_traffic_authorized"] is True
    assert partial["call_action_enabled"] is False
    assert partial["published"] is False
    p["activation_gates"]["founder_live_traffic_authorized"] = "unverified"
    with pytest.raises(ValueError, match="invalid_partner_launch_gates"):
        build_partner_landing_review(p)


def test_private_partner_preview_materializer_does_not_publish_or_leak(tmp_path):
    from scripts.reconcile_buyer_email_relationships import materialize_partner_private_reviews
    from empire_os.commercial_relationship_registry import PARTNER_LAUNCH_GATES
    import pytest
    import json
    from pathlib import Path

    base=tmp_path/"runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    asset=tmp_path/"templates/lead_smart/roofing/roofing-hero.webp"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"RIFF"+b"\x0c\x00\x00\x00"+b"WEBP"+b"VP8 "+b"X"*20)
    rows=[]
    for key in ("leadbank","validated","connexis"):
        rows.append({
            "entity_key":key,
            "company":key,
            "activation_gates": {x:False for x in PARTNER_LAUNCH_GATES},
            "technical_review_packet":{
                "entity_key":key,
                "lead_smart_route_or_number_inherited": False,
                "traffic_enabled":False,
                "execution_authority":"NONE",
                "partner_tracking_number":None,
                "routing_destination_or_sip_endpoint":None,
                "signed_agreement_evidence":None,
            },
        })
    result=materialize_partner_private_reviews(tmp_path,{"partner_pilot_readiness_queue":rows})
    assert result["review_file_count"]==3
    assert result["no_public_web_route_created"] is True
    assert result["execution_authority"]=="NONE"
    for row in result["artifacts"]:
        p=tmp_path/row["relative_private_html_path"]
        assert p.exists() and (p.stat().st_mode & 0o777)==0o600
        assert (p.parent.stat().st_mode & 0o777)==0o700
        assert (p.parent/"review.json").stat().st_mode & 0o777==0o600
        content=p.read_text()
        assert "<form" not in content and "tel:" not in content
        assert "noindex,nofollow" in content
    assert not (tmp_path/"apps").exists()
    assert not (tmp_path/"templates/lead_smart/roofing/page.tsx").exists()
    # Repeated scheduled refresh is content-idempotent.
    assert result == materialize_partner_private_reviews(tmp_path,{"partner_pilot_readiness_queue":rows})
    p=base/"partner_private_reviews/validated/index.html"
    p.unlink()
    p.symlink_to(tmp_path/"templates/lead_smart/roofing/roofing-hero.webp")
    with pytest.raises(ValueError, match="unsafe_private_preview_destination"):
        materialize_partner_private_reviews(tmp_path,{"partner_pilot_readiness_queue":rows})


def test_offline_buyer_preview_has_two_separate_noncollecting_products():
    from empire_os.buyer_pilot_assets import (
        build_partner_landing_review, render_partner_landing_review_html,
    )
    from empire_os.commercial_relationship_registry import (
        PARTNER_LAUNCH_GATES, PARTNER_PILOT_SCOPES, partner_technical_review_packet,
    )
    for key, spec in PARTNER_PILOT_SCOPES.items():
        packet = partner_technical_review_packet(
            key, spec, {"last_inbound_message_id": None, "gmail_thread_ids": []}
        )
        pilot = {
            "entity_key": key, "company": key,
            "activation_gates": {gate: False for gate in PARTNER_LAUNCH_GATES},
            "technical_review_packet": packet,
        }
        review = build_partner_landing_review(pilot)
        a = review["two_product_pilot_review"]
        assert a["PAY_PER_CALL"]["route_enabled"] is False
        assert a["PAY_PER_LEAD"]["consumer_fields_collected"] is False
        assert a["PAY_PER_LEAD"]["form_enabled"] is False
        assert a["PAY_PER_LEAD"]["delivery_enabled"] is False
        assert a["same_enquiry_double_sale_approved"] is False
        assert a["canonical_consumer_lead_receipt_verified"] is False
        markup = render_partner_landing_review_html(review)
        assert "Pay Per Call — under review" in markup
        assert "Pay Per Lead — under review" in markup
        assert "Consent text/evidence" in markup
        assert "duplicate call/form enquiry" in markup
        assert "<form" not in markup.lower()
        assert "tel:" not in markup.lower()
        assert "<script" not in markup.lower()
        assert "http://" not in markup.lower()
        assert "https://" not in markup.lower()
        assert 'disabled aria-disabled="true"' in markup


def test_offline_product_review_rejects_true_capture_and_delivery_flags():
    import copy
    import pytest
    from empire_os.buyer_pilot_assets import (
        build_partner_landing_review, render_partner_landing_review_html,
    )
    from empire_os.commercial_relationship_registry import (
        PARTNER_LAUNCH_GATES, PARTNER_PILOT_SCOPES, partner_technical_review_packet,
    )
    spec = PARTNER_PILOT_SCOPES["connexis"]
    packet = partner_technical_review_packet(
        "connexis", spec,
        {"last_inbound_message_id": None, "gmail_thread_ids": []},
    )
    pilot = {
        "entity_key": "connexis", "company": "Connexis",
        "activation_gates": {gate: False for gate in PARTNER_LAUNCH_GATES},
        "technical_review_packet": packet,
    }
    clean = build_partner_landing_review(pilot)
    for product, field in (
        ("PAY_PER_LEAD", "live_form_capture_enabled"),
        ("PAY_PER_LEAD", "lead_delivery_enabled"),
        ("PAY_PER_CALL", "live_call_traffic_enabled"),
    ):
        unsafe = copy.deepcopy(pilot)
        unsafe["technical_review_packet"]["publisher_format_review"][product][field] = True
        with pytest.raises(ValueError, match="live_format_authority_forbidden"):
            build_partner_landing_review(unsafe)
    for product, field in (
        ("PAY_PER_LEAD", "form_enabled"),
        ("PAY_PER_LEAD", "delivery_enabled"),
        ("PAY_PER_CALL", "route_enabled"),
    ):
        unsafe = copy.deepcopy(clean)
        unsafe["two_product_pilot_review"][product][field] = True
        with pytest.raises(ValueError, match="private_review_rejects_enabled"):
            render_partner_landing_review_html(unsafe)
