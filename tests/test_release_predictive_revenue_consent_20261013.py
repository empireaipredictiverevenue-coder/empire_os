"""Offline negative-only acceptance and atomic rollback tests for one-page release."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts import release_predictive_revenue_consent_20261013 as release


def _body(x):
    return json.dumps({"detail": x}).encode("utf-8")


def test_negative_requests_prove_exact_consent_and_never_use_valid_product(monkeypatch):
    observed = []

    def fake_http(path, *, method="GET", payload=None, origin=False):
        observed.append((path, method, payload, origin))
        assert method == "POST"
        assert payload["product_code"] == "not-an-empire-offer-consent-negative-20261013"
        assert payload["email"].endswith(".invalid")
        assert payload["domain"] == "example.invalid"
        if "contact_consent" not in payload:
            return 422, _body([{"loc": ["body", "contact_consent"], "type": "missing"}])
        if payload["contact_consent"] is False or payload.get("website"):
            return 422, _body("specific_contact_consent_required")
        raise AssertionError("never send an allowed, valid test prospect")

    monkeypatch.setattr(release, "http", fake_http)
    result = release.invalid_api_proofs()
    assert result == {
        "missing_consent": 422,
        "false_consent": 422,
        "bot_honeypot": 422,
        "gateway_false_consent": 422,
    }
    assert len(observed) == 4
    assert observed[-1][3] is True
    assert all(not x[3] for x in observed[:3])


@pytest.mark.parametrize("response", [
    _body("invalid_product_code"),
    _body("old_backend_no_consent_support"),
    b'{"detail": "malformed"}',
])
def test_old_handler_or_wrong_reason_fails_closed(monkeypatch, response):
    monkeypatch.setattr(release, "http", lambda *a, **k: (422, response))
    with pytest.raises(release.ReleaseHeld):
        release.invalid_api_proofs()


def test_success_with_non_422_never_proves_gate(monkeypatch):
    monkeypatch.setattr(release, "http", lambda *a, **k: (200, b'{}'))
    with pytest.raises(release.ReleaseHeld, match="BACKEND_NEGATIVE_GATE_FAILED"):
        release.invalid_api_proofs()


def test_atomic_page_change_and_rollback_in_temporary_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "LIVE", tmp_path)
    p = tmp_path / "predictive-revenue.html"
    old = b"old static page"
    new = b"new consent static page"
    p.write_bytes(old)
    release.atomic_page(new, release.sha(old), release.sha(new))
    assert p.read_bytes() == new
    release.atomic_page(old, release.sha(new), release.sha(old))
    assert p.read_bytes() == old


def test_atomic_page_blocks_changed_production(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "LIVE", tmp_path)
    p = tmp_path / "predictive-revenue.html"
    p.write_bytes(b"another agent's newer page")
    with pytest.raises(release.ReleaseHeld, match="CONCURRENT_PAGE_CHANGE_BLOCKED"):
        release.atomic_page(b"replacement", release.sha(b"old"), release.sha(b"replacement"))
    assert p.read_bytes() == b"another agent's newer page"


def test_release_requires_exact_apply_flag_without_touching_service(monkeypatch):
    monkeypatch.setattr(release, "eligible_manifest", lambda: {"new_assets": 2})
    monkeypatch.setattr(release, "current_health", lambda: {
        "payment_execution": False
    })
    monkeypatch.setattr(release, "apply", lambda _: pytest.fail("must not apply"))
    monkeypatch.setattr("sys.argv", ["prog", "--apply"])
    assert release.main() == 2


def test_default_mode_is_read_only(monkeypatch, capsys):
    monkeypatch.setattr(release, "eligible_manifest", lambda: {"new_assets": 2})
    monkeypatch.setattr(release, "current_health", lambda: {
        "payment_execution": False
    })
    monkeypatch.setattr(release, "apply", lambda _: pytest.fail("must not apply"))
    monkeypatch.setattr("sys.argv", ["prog", "--check"])
    assert release.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "READ_ONLY_RELEASE_PREFLIGHT_PASS"
    assert result["restart_performed"] is False
    assert result["outbound_sent"] is False


def test_existing_offer_catalogs_proved_without_payment_or_write(monkeypatch):
    seen = []

    def catalog_http(path):
        seen.append(path)
        if path == "/v1/catalog":
            return 200, json.dumps({"count": 4, "products": [{}, {}, {}, {}]}).encode()
        if path == "/v1/predictive-revenue/products":
            return 200, json.dumps({"product_count": 5, "products": [{}, {}, {}, {}, {}]}).encode()
        raise AssertionError("unexpected path")

    monkeypatch.setattr(release, "http", catalog_http)
    assert release.existing_catalog_proofs() == {
        "/v1/catalog": 4, "/v1/predictive-revenue/products": 5
    }
    assert seen == ["/v1/catalog", "/v1/predictive-revenue/products"]


def test_offer_catalog_drift_refuses_release(monkeypatch):
    monkeypatch.setattr(release, "http", lambda path: (
        200, json.dumps({"count": 0, "products": []}).encode()
    ))
    with pytest.raises(release.ReleaseHeld, match="CURRENT_REVENUE_CATALOG_CHANGED"):
        release.existing_catalog_proofs()


def test_unprivileged_operator_cannot_restart(monkeypatch):
    monkeypatch.setattr(release.os, "geteuid", lambda: 1000)
    with pytest.raises(release.ReleaseHeld, match="ROOT_OPERATOR_REQUIRED"):
        release.apply({})


def test_publish_only_reuses_live_consent_backend_without_restarting_service(
    monkeypatch, tmp_path
):
    root = tmp_path / "site"
    stage = tmp_path / "stage"
    (root / "_next/static/css").mkdir(parents=True)
    (root / "_next/static/chunks/app/predictive-revenue").mkdir(parents=True)
    (stage / "after").mkdir(parents=True)
    old, new = b"old public html", b"new consent html"
    (root / release.PAGE).write_bytes(old)
    (stage / "after" / release.PAGE).write_bytes(new)
    assets = {}
    for asset in (
        "_next/static/css/unique-consent.css",
        "_next/static/chunks/app/predictive-revenue/unique-consent.js",
    ):
        payload = asset.encode()
        source = stage / "assets" / asset
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
        assets[asset] = {"sha256": release.sha(payload), "live_present": False}
    manifest = {
        "old_page_sha256": release.sha(old),
        "new_page_sha256": release.sha(new),
        "assets": assets,
    }
    monkeypatch.setattr(release, "LIVE", root)
    monkeypatch.setattr(release, "STAGE", stage)
    monkeypatch.setattr(release, "current_health", lambda: {
        "payment_proposal_authorized": True,
        "binding_order_creation_authorized": True,
        "payment_execution": False,
        "revenue_recognition": False,
        "checkout_settlement_mode": "direct",
        "bsc_payment_configuration_status": "BSC_CONFIGURED_CHAIN_UNVERIFIED",
        "founder_led_commercial_interest_enabled": True,
    })
    monkeypatch.setattr(release, "existing_catalog_proofs", lambda: {
        "/v1/catalog": 4, "/v1/predictive-revenue/products": 5
    })
    monkeypatch.setattr(release, "invalid_api_proofs", lambda: {
        "missing_consent": 422, "false_consent": 422,
        "bot_honeypot": 422, "gateway_false_consent": 422,
    })
    monkeypatch.setattr(release, "eligible_manifest", lambda: manifest)
    monkeypatch.setattr(release, "public_readback", lambda _: {
        "new_page": 200, "new_assets": 2, "sha256_verified": True
    })
    monkeypatch.setattr(release.subprocess, "run",
                        lambda *a, **kw: pytest.fail("no systemctl restart permitted"))
    receipt = release.apply(manifest, publish_only_if_backend_live=True)
    assert receipt["status"] == "PREDICTIVE_REVENUE_CONSENT_LIVE_VERIFIED"
    assert receipt["checkout_service_restarted"] is False
    assert receipt["payment_authority_unchanged"] is True
    assert (root / release.PAGE).read_bytes() == new
    assert (stage / "receipt.json").is_file()
    for key in assets:
        assert (root / key).is_file()
