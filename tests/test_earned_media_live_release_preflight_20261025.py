"""Original live GET evidence is not a private release or a buyer conversion."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from empire_os.earned_media_live_release_preflight import (
    CANARY_SCHEMA, SCHEMA, assess_release, inspect_live_release,
)
from scripts.review_earned_media_advisory_bridge_20261025 import main
from tests.test_earned_media_leadgen_review_20261025 import _packet


def conversion():
    return {
        "schema_version": "empire.earned_media.first_party_conversion_review.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "state": "STAGED_EXISTING_GUIDE_TO_EXISTING_INTAKE_NOT_LIVE_VERIFIED",
        "reviewed_entry_page": "/predictive-revenue",
        "source_code_readiness": True,
        "founder_site_release_authorized": False,
        "consented_enquiry_verified": False,
        "realised_revenue_verified": False,
        "publication_executed": False,
        "smart_crm_writes": False,
    }


def public():
    return {
        "schema_version": CANARY_SCHEMA, "mode": "READ_ONLY",
        "status": "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN",
        "public_page_count": 2, "compiled_intake_routes_verified": 2,
        "commercial_offer_count": 10, "predictive_revenue_product_count": 5,
        "database_writes": False, "genuine_test_buyer_submitted": False,
        "founder_crm_delivery_verified": False,
        "outbound_sent": False, "checkout_or_payment_executed": False,
    }


def crm():
    return {
        "private_crm_auth_boundary_checked": True,
        "private_crm_auth_boundary_verified": True,
        "private_crm_healthy": True,
        "anonymous_prospect_access_denied": True,
        "anonymous_buyer_access_denied": True,
        "private_crm_customer_rows_read": False,
        "founder_login_authenticated": False,
        "founder_crm_delivery_verified": False,
    }


def test_live_public_and_private_crm_get_checks_never_approve_release():
    out = assess_release(conversion(), public=public(), private_crm=crm())
    assert out["schema_version"] == SCHEMA
    assert out["source_code_review_ready"] is True
    assert out["public_original_enquiry_gets_verified"] is True
    assert out["private_crm_anonymous_denial_verified"] is True
    assert out["private_founder_console_ingress_verified"] is False
    assert out["new_staged_cta_deployed_verified"] is False
    assert out["launch_approval"] is False
    assert out["source_attributed_consented_enquiry_verified"] is False
    assert out["realised_revenue_gbp_minor"] is None
    assert out["messages_sent"] is False
    assert out["database_writes"] is False
    assert out["release_hold_reasons"] == [
        "PRIVATE_FOUNDER_INGRESS_AND_SESSION_NOT_INDEPENDENTLY_VERIFIED",
        "SITE_OWNER_ASTRA_AND_FOUNDER_RELEASE_NOT_APPROVED",
        "ACTUAL_DEPLOYED_NEW_CTA_AND_NEW_PRIVATE_ROUTE_UNVERIFIED",
    ]


def test_fake_caller_claim_of_private_ingress_cannot_clear_hold():
    out = assess_release(
        conversion(), public=public(), private_crm=crm(),
        private_founder_ingress_verified=True,
    )
    assert out["private_founder_console_ingress_verified"] is False
    assert out["launch_approval"] is False
    assert out["status"] == "HELD_PRIVATE_AUTH_AND_PRODUCTION_RELEASE"


@pytest.mark.parametrize("field,value", [
    ("status", "ALL_BUYERS_VERIFIED"),
    ("public_page_count", 1),
    ("commercial_offer_count", True),
    ("genuine_test_buyer_submitted", True),
    ("database_writes", True),
    ("founder_crm_delivery_verified", True),
])
def test_bad_public_route_evidence_held(field, value):
    altered = public()
    altered[field] = value
    out = assess_release(conversion(), public=altered, private_crm=crm())
    assert out["public_original_enquiry_gets_verified"] is False
    assert "PUBLIC_FIRST_PARTY_GET_CANARY_UNVERIFIED" in out["release_hold_reasons"]


@pytest.mark.parametrize("field,value", [
    ("anonymous_prospect_access_denied", False),
    ("anonymous_buyer_access_denied", False),
    ("private_crm_customer_rows_read", True),
    ("private_crm_auth_boundary_verified", None),
])
def test_bad_private_crm_anonymous_access_fails(field, value):
    altered = crm()
    altered[field] = value
    out = assess_release(conversion(), public=public(), private_crm=altered)
    assert out["private_crm_anonymous_denial_verified"] is False
    assert "EXISTING_PRIVATE_CRM_ANONYMOUS_BOUNDARY_UNVERIFIED" in out["release_hold_reasons"]


def test_changed_or_unready_guide_fails_source():
    altered = conversion()
    altered["consented_enquiry_verified"] = True
    out = assess_release(altered, public=public(), private_crm=crm())
    assert out["source_code_review_ready"] is False
    assert "ORIGINAL_CONTENT_CONVERSION_SOURCE_HELD" in out["release_hold_reasons"]


def test_network_errors_are_bounded_and_do_not_fabricate_proof():
    def forbidden():
        raise OSError("private error with secrets")
    out = inspect_live_release(conversion(), public_inspector=forbidden,
                               crm_inspector=forbidden)
    assert out["public_original_enquiry_gets_verified"] is False
    assert out["private_crm_anonymous_denial_verified"] is False
    assert "secrets" not in json.dumps(out)
    assert out["launch_approval"] is False


def test_injected_get_only_original_canary_functions():
    calls = []
    def p():
        calls.append("public_get")
        return public()
    def c():
        calls.append("private_anonymous_get")
        return crm()
    out = inspect_live_release(conversion(), public_inspector=p, crm_inspector=c)
    assert calls == ["public_get", "private_anonymous_get"]
    assert out["public_original_enquiry_gets_verified"] is True
    assert out["private_crm_anonymous_denial_verified"] is True
    assert out["launch_approval"] is False


def test_explicit_live_flag_preserves_fail_closed_shell_exit(monkeypatch, tmp_path, capsys):
    root, pr, _ = _packet(tmp_path)
    calls = []
    def fake_live(guide):
        calls.append(guide)
        return assess_release(guide, public=public(), private_crm=crm())
    from empire_os import earned_media_live_release_preflight as mod
    monkeypatch.setattr(mod, "inspect_live_release", fake_live)
    args = [
        "--review-only", "--with-leadgen", "--summary",
        "--live-release-preflight", "--repo-root", str(root),
        "--pr-root", str(pr), "--distribution-root", str(root),
    ]
    assert main(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert len(calls) == 1
    assert result["live_release_preflight"]["status"] == (
        "HELD_PRIVATE_AUTH_AND_PRODUCTION_RELEASE"
    )
    assert result["live_release_preflight"]["private_founder_console_ingress_verified"] is False
    assert result["revenue_verified"] is False


def test_normal_founder_review_does_not_perform_live_network_checks(monkeypatch, tmp_path, capsys):
    root, pr, _ = _packet(tmp_path)
    from empire_os import earned_media_live_release_preflight as mod
    def forbidden(_):
        pytest.fail("opt-in only network canary must not run")
    monkeypatch.setattr(mod, "inspect_live_release", forbidden)
    args = [
        "--review-only", "--with-leadgen", "--summary",
        "--repo-root", str(root),
        "--pr-root", str(pr), "--distribution-root", str(root),
    ]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["live_release_preflight"] is None
