"""First-sale control: original counts, checkout, legacy snapshot and replay."""
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from empire_os.first_sale_live_conversion_observer import (
    SCHEMA, evaluate_first_sale_readiness, observe_first_sale_readiness,
)

NOW = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)


def owner_counts(n=0, **changes):
    data = {
        "schema_version": "empire.founder.canonical_sales_source_aggregate.v1",
        "mode": "OBSERVE",
        "source": "CANONICAL_EMPIREDB",
        "read_only": True,
        "status": (
            "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE" if n == 0
            else "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED"
        ),
        "execution_authority": "NONE",
        "customer_rows_disclosed": False,
        "contact_data_disclosed": False,
        "tenant_identifier_disclosed": False,
        "database_writes": False,
        "outbound_sent": False,
        "payment_action": False,
        "commercial_acquisition_rows": n,
        "predictive_acquisition_rows": 0,
        "sales_acquisition_rows": n,
        "distinct_sales_prospects": n,
        "source_evidence_consistent_rows": n,
        "entity_unlinked_acquisition_rows": 0,
        "founder_binding_exact_one_rows": n,
        "founder_binding_missing_or_ambiguous_rows": 0,
        "buyer_contact": "private@example.invalid",
    }
    data.update(changes)
    return data


def checkout(**changes):
    data = {
        "status": "online",
        "service": "empire-self-serve-checkout",
        "payment_execution": False,
        "revenue_recognition": False,
        "founder_led_commercial_interest_enabled": True,
        "binding_order_creation_authorized": True,
        "payment_proposal_authorized": True,
        "checkout_settlement_mode": "direct",
        "bsc_payment_configuration_status": "BSC_CONFIGURED_CHAIN_UNVERIFIED",
        "email": "hidden@example.invalid",
    }
    data.update(changes)
    return data


def review(n=0, previous=None, **changes):
    return evaluate_first_sale_readiness(
        sales=owner_counts(n=n, **changes),
        checkout=checkout(),
        funnel_freshness="STALE_OR_FUTURE",
        previous=previous,
    )


def test_absence_is_confirmed_live_enquiry_absence_not_absence_of_all_sales():
    r = review()
    assert r["schema_version"] == SCHEMA
    assert r["status"] == "NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES"
    assert r["canonical_sales_acquisition_counts"]["sales_acquisition_rows"] == 0
    assert r["next_existing_owner_action"] == "CHECK_ORIGINAL_FIRST_PARTY_INTAKE_AND_WEB_CONVERSION"
    assert r["legacy_founder_funnel_snapshot_freshness"] == "STALE_OR_FUTURE"
    assert r["old_funnel_counts_used_as_current"] is False
    assert r["canonical_order_or_settlement_evidence_checked"] is False
    assert r["verified_first_sale"] is None
    assert r["recognized_revenue_cents"] is None
    assert r["outbound_sent"] is False
    assert "hidden@" not in str(r) and "private@" not in str(r)


def test_new_owner_enquiry_is_owner_review_not_authenticated_order():
    initial = review()
    changed = review(1, previous=initial)
    assert changed["status"] == "FIRST_PARTY_ENQUIRY_PRESENT_OWNER_REVIEW_REQUIRED"
    assert changed["transition"] == "FIRST_SALE_SOURCE_CHANGE_OWNER_REVIEW_REQUIRED"
    assert changed["canonical_sales_acquisition_counts"]["distinct_sales_prospects"] == 1
    assert changed["verified_first_sale"] is None
    assert changed["payment_action"] is False
    assert changed["next_existing_owner_action"] == "EXISTING_SALES_CRM_OWNER_REVIEW_ORIGINAL_ENQUIRY"
    repeated = review(1, previous=changed)
    assert repeated["transition"] == "UNCHANGED_FIRST_SALE_EVIDENCE_HOLD"
    assert repeated["repeated_owner_attention_suppressed"] is True


def test_unlinked_first_party_buyer_goes_to_existing_identity_owner():
    r = review(
        1, founder_binding_exact_one_rows=0,
        founder_binding_missing_or_ambiguous_rows=1,
    )
    assert r["status"] == "FIRST_PARTY_ENQUIRY_TO_FOUNDER_BINDING_HOLD"
    assert r["crm_mutations"] is False


@pytest.mark.parametrize("mutation", [
    {"contact_data_disclosed": True},
    {"execution_authority": "send"},
    {"read_only": False},
    {"commercial_acquisition_rows": 7},
    {"source_evidence_consistent_rows": 8},
    {"founder_binding_exact_one_rows": 5},
    {"sales_acquisition_rows": -1},
    {"commercial_acquisition_rows": "1"},
    {"status": "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED"},
])
def test_untrusted_or_contradictory_aggregate_never_becomes_sales(mutation):
    source = owner_counts(0, **mutation)
    r = evaluate_first_sale_readiness(
        sales=source, checkout=checkout(),
        funnel_freshness="STALE_OR_FUTURE",
    )
    assert r["status"] == "FIRST_PARTY_CANONICAL_SOURCE_UNVERIFIED"
    assert r["canonical_sales_acquisition_counts"] is None
    assert r["recognized_revenue_cents"] is None


@pytest.mark.parametrize("change", [
    {"revenue_recognition": True},
    {"payment_execution": True},
    {"service": "another-service"},
    {"founder_led_commercial_interest_enabled": False},
])
def test_checkout_mismatch_is_held_not_payment_authority(change):
    r = evaluate_first_sale_readiness(
        sales=owner_counts(), checkout=checkout(**change), funnel_freshness="FRESH",
    )
    assert r["checkout_status"] == "CHECKOUT_OR_ENQUIRY_HEALTH_UNVERIFIED"
    assert r["payment_action"] is False


def test_funnel_snapshot_staleness_and_privacy_without_using_its_counts(tmp_path):
    file = tmp_path / "runtime/commercial_funnel/latest.json"
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps({
        "schema_version": "empire.founder_commercial_funnel.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "generated_at": "2026-09-22T14:49:47+00:00",
        "counts": {"prospect_acquisitions": 493, "outbound_delivered": 88},
        "buyer_email": "private@example.invalid",
    }))
    read = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=None,
        sales_probe=lambda: owner_counts(),
        health_probe=checkout,
    )
    assert read["legacy_founder_funnel_snapshot_freshness"] == "STALE_OR_FUTURE"
    assert read["canonical_sales_acquisition_counts"]["sales_acquisition_rows"] == 0
    assert "493" not in str(read)
    assert "private@" not in str(read)
    file.write_text(json.dumps({
        "schema_version": "empire.founder_commercial_funnel.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "generated_at": NOW.isoformat(),
    }))
    fresh = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=read,
        sales_probe=lambda: owner_counts(), health_probe=checkout,
    )
    assert fresh["legacy_founder_funnel_snapshot_freshness"] == "FRESH"


def test_sandbox_has_no_db_or_network_and_no_contact_egress(tmp_path, monkeypatch):
    import empire_os.first_sale_live_conversion_observer as module
    monkeypatch.setattr(module, "_canonical_sales_counts",
                        lambda: pytest.fail("sandbox must not query EmpireDB"))
    monkeypatch.setattr(module, "_checkout_health",
                        lambda: pytest.fail("sandbox must not hit checkout"))
    record = observe_first_sale_readiness(root=tmp_path, now=NOW, previous=None)
    assert record["status"] == "FIRST_PARTY_CANONICAL_SOURCE_UNVERIFIED"
    assert record["outbound_sent"] is False
    assert record["canonical_sales_acquisition_counts"] is None


def test_provenance_errors_do_not_expose_secret_payload_or_raise(tmp_path):
    def broken(): raise RuntimeError("tenant=secret, email=private@example.invalid")
    out = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=None,
        sales_probe=broken, health_probe=broken,
    )
    assert out["status"] == "FIRST_PARTY_CANONICAL_SOURCE_UNVERIFIED"
    assert out["checkout_status"] == "CHECKOUT_OR_ENQUIRY_HEALTH_UNVERIFIED"
    assert "private@" not in str(out)
    assert "secret" not in str(out)


def test_public_site_get_canary_never_submits_buyer_or_payment(monkeypatch):
    from email.message import Message
    import urllib.error
    import empire_os.first_sale_live_conversion_observer as source

    observed = []
    class Response:
        def __init__(self, status, content):
            self.status = status
            self.headers = Message()
            self.headers.add_header("Content-Type", content)
        def __enter__(self):
            return self
        def __exit__(self, *_exc):
            return False

    def get_only(request, timeout):
        observed.append((request.full_url, request.get_method(), timeout))
        assert request.get_method() == "GET"
        assert request.get_header("Host") == "empire-ai.co.uk"
        if request.full_url.endswith(("/interests", "/orders")):
            headers = Message()
            headers.add_header("Content-Type", "application/json")
            raise urllib.error.HTTPError(request.full_url, 405, "Method Not Allowed", headers, None)
        return Response(
            200,
            "text/html" if request.full_url.endswith(("/commercial", "/buy"))
            else "application/json",
        )
    monkeypatch.setattr(source.urllib.request, "urlopen", get_only)
    assert source._public_conversion_gets() is True
    assert len(observed) == 6
    assert all(method == "GET" for _,method,_ in observed)


def test_site_conversion_routing_drift_requests_existing_owner_not_fake_sales(tmp_path):
    owner = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=None,
        sales_probe=owner_counts,
        health_probe=checkout,
        public_probe=lambda: False,
    )
    assert owner["public_conversion_route_status"] == "PUBLIC_CONVERSION_ROUTE_REVIEW_REQUIRED"
    assert owner["next_existing_owner_action"] == "WEBSITE_CONVERSION_ROUTE_OWNER_REPAIR"
    assert owner["public_post_or_customer_submission_attempted"] is False
    restored = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=owner,
        sales_probe=owner_counts,
        health_probe=checkout,
        public_probe=lambda: True,
    )
    assert restored["public_conversion_route_status"] == "PUBLIC_CONVERSION_GET_ROUTES_PRESENT_POST_UNTESTED"
    assert restored["transition"] == "FIRST_SALE_SOURCE_CHANGE_OWNER_REVIEW_REQUIRED"
    assert restored["verified_first_sale"] is None


def test_legacy_buy_asset_mismatch_is_held_not_silently_rehashed(tmp_path):
    preview = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=None,
        sales_probe=owner_counts, health_probe=checkout,
        public_probe=lambda: True,
        asset_probe=lambda: False,
    )
    assert preview["status"] == "NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES"
    assert preview["public_conversion_route_status"] == (
        "PUBLIC_CONVERSION_GET_ROUTES_PRESENT_POST_UNTESTED"
    )
    assert preview["legacy_buy_ui_manifest_integrity_status"] == (
        "LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD"
    )
    assert preview["legacy_buy_ui_manifest_rewrite_authorized"] is False
    assert preview["next_existing_owner_action"] == (
        "EXISTING_CHECKOUT_WEBSITE_RELEASE_OWNER_RECONCILE_HTML_PIN"
    )
    repeated = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=preview,
        sales_probe=owner_counts, health_probe=checkout,
        public_probe=lambda: True, asset_probe=lambda: False,
    )
    assert repeated["transition"] == "UNCHANGED_FIRST_SALE_EVIDENCE_HOLD"
    assert repeated["repeated_owner_attention_suppressed"] is True


def test_original_legacy_asset_verifier_failure_is_private_and_nonexecuting(tmp_path):
    def broken():
        raise ValueError("hash drift at hidden/private@example.invalid")
    preview = observe_first_sale_readiness(
        root=tmp_path, now=NOW, previous=None,
        sales_probe=owner_counts, health_probe=checkout,
        public_probe=lambda: True, asset_probe=broken,
    )
    assert preview["legacy_buy_ui_manifest_integrity_status"] == (
        "LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD"
    )
    assert preview["legacy_buy_ui_manifest_rewrite_authorized"] is False
    assert preview["recognized_revenue_cents"] is None
    assert preview["outbound_sent"] is False
    assert "private@" not in str(preview)
