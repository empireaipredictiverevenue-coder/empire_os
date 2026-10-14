"""Live first-party enquiry canary uses GET only, no submissions or revenue claims."""
import json
from urllib.request import Request

import pytest

from scripts import probe_first_party_sales_http_readonly as canary


def fake_fetch(*, missing_endpoint=False, wrong_authority=False,
               script_missing=False, bad_catalog=False,
               fail_path=None, external_script=False):
    visited = []

    def fetch(path, max_bytes):
        visited.append((path, max_bytes))
        if path == fail_path:
            raise canary.CanaryHeld("LOCAL_READONLY_ENDPOINT_UNAVAILABLE")
        if path in ("/commercial", "/predictive-revenue"):
            marker = ("commercial" if path == "/commercial" else "predictive")
            extra = '<script src="https://evil.example/collect.js"></script>' if external_script else ""
            src = f"/_next/static/chunks/{marker}.js"
            html = f'<html><head>{extra}<script src="{src}"></script></head></html>'
            return 200, "text/html; charset=utf-8", html.encode()
        if path.startswith("/_next/static/chunks/"):
            if script_missing:
                return 404, "text/html", b"Not Found"
            endpoint = (
                "/v1/checkout/commercial/interests"
                if "commercial.js" in path
                else "/v1/checkout/predictive-revenue/interests"
            )
            if missing_endpoint:
                endpoint = "/v1/checkout/not-an-enquiry"
            return 200, "application/javascript", f'fetch("{endpoint}")'.encode()
        if path == "/v1/checkout/commercial/offers":
            item = {
                "status": "FOUNDER_LED_ENQUIRY_AVAILABLE",
                "scope": "BUYER_INITIATED_CONTACT_ONLY",
                "outbound_authority": "send" if wrong_authority else "none",
                "payment_authority": "none",
                "checkout_authorized": False,
                "actual_revenue": False,
                "count": 1,
                "offers": [{"product_code": "approved_consultancy"}],
            }
            if bad_catalog:
                item["count"] = 2
            return 200, "application/json", json.dumps(item).encode()
        if path == "/v1/checkout/predictive-revenue/products":
            return 200, "application/json", json.dumps({
                "execution_authority": "none",
                "actual_revenue": False,
                "product_count": 1,
                "products": [{"product_code": "approved_predictive_product"}],
            }).encode()
        raise AssertionError("EXTERNAL_OR_UNEXPECTED_CALL:" + path)

    return fetch, visited


def test_complete_read_only_surface_proof_never_claims_crm_delivery():
    fetch, visited = fake_fetch()
    report = canary.inspect(fetch)
    assert report["status"] == "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN"
    assert report["compiled_intake_routes_verified"] == 2
    assert report["commercial_offer_count"] == 1
    assert report["predictive_revenue_product_count"] == 1
    assert report["canonical_sales_acquisitions_checked"] is False
    assert report["founder_crm_delivery_verified"] is False
    assert report["genuine_test_buyer_submitted"] is False
    assert report["database_writes"] is False
    assert report["outbound_sent"] is False
    assert len(visited) == 6


@pytest.mark.parametrize("fixture,expected", [
    ({"missing_endpoint": True}, "DEPLOYED_ENQUIRY_FORM_ACTION_NOT_FOUND"),
    ({"wrong_authority": True}, "COMMERCIAL_CATALOG_AUTHORITY_OR_COUNT_DRIFT"),
    ({"bad_catalog": True}, "COMMERCIAL_CATALOG_AUTHORITY_OR_COUNT_DRIFT"),
    ({"script_missing": True}, "DEPLOYED_APP_SCRIPT_UNAVAILABLE"),
    ({"fail_path": "/commercial"}, "LOCAL_READONLY_ENDPOINT_UNAVAILABLE"),
])
def test_missing_or_untrusted_surface_is_held(fixture, expected):
    fetch, _ = fake_fetch(**fixture)
    report = canary.inspect(fetch)
    assert report["status"] == "HELD"
    assert report["reason_code"] == expected
    assert report["founder_crm_delivery_verified"] is False
    assert report["database_writes"] is False


def test_external_scripts_are_ignored():
    fetch, visited = fake_fetch(external_script=True)
    report = canary.inspect(fetch)
    assert report["compiled_intake_routes_verified"] == 2
    assert not any(path.startswith("http") for path, _ in visited)
    assert len(visited) == 6


@pytest.mark.parametrize("path", [
    "//example.com/path",
    "/_next/static/../secret.js",
    "/_next/static/key.js?token=any",
    "/_next/static/key.js#fragment",
    "/bad\\evil",
])
def test_get_canary_rejects_untrusted_paths_before_network(monkeypatch, path):
    monkeypatch.setattr(canary, "build_opener", lambda *a: (
        (_ for _ in ()).throw(AssertionError("NETWORK_FORBIDDEN"))))
    with pytest.raises(canary.CanaryHeld, match="UNSAFE_LOCAL_GET_PATH"):
        canary.fetch_local_get(path, 999)


def test_compiled_script_manifest_has_hard_count():
    def excessive(path, cap):
        if path == "/commercial":
            html = "<html>" + "".join(
                '<script src="/_next/static/chunks/chunk' + str(i) + '.js"></script>'
                for i in range(canary.MAX_SCRIPTS_PER_PAGE + 1)
            ) + "</html>"
            return 200, "text/html", html.encode()
        raise AssertionError("SHOULD_STOP_BEFORE_SECOND_REQUEST")
    report = canary.inspect(excessive)
    assert report["reason_code"] == "PAGE_SCRIPT_MANIFEST_MISSING_OR_OVERSIZED"


def test_actual_http_transport_declares_get_only(monkeypatch):
    methods = []
    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/html"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, cap):
            return b"<html></html>"
    class FakeOpener:
        def open(self, req, timeout):
            assert isinstance(req, Request)
            methods.append(req.get_method())
            assert req.headers.get("Host") == canary.PUBLIC_HOST
            assert req.full_url.startswith(canary.ORIGIN + "/")
            return FakeResponse()
    monkeypatch.setattr(canary, "build_opener", lambda *args: FakeOpener())
    status, _, payload = canary.fetch_local_get("/commercial", 400_000)
    assert status == 200
    assert payload == b"<html></html>"
    assert methods == ["GET"]


def test_no_customer_payload_is_ever_created_by_canary():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(canary.__file__).read_text())
    literals = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not any("POST" == value for value in literals)
    assert not any("ingest_prospect_atomic" == value for value in literals)
    assert canary.ORIGIN == "http://127.0.0.1"
