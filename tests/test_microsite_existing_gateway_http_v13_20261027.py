"""V13: real existing FastAPI /research/ GET+HEAD owner route rehearsal.

This exercises the unmodified public gateway and its original five-release
reader. A monkeypatched fallback exists ONLY inside pytest, never on disk or
in the running gateway. Synthetic approvals here are only test fixtures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from empire_os.public_gateway import app
from empire_os import owned_campaign_release as original
from empire_os.microsite_original_gateway_addendum_v12 import (
    SCHEMA, APPROVAL_SCHEMA, ORIGINAL_PREVIEW_SHA, CAMPAIGN_ID,
    CANDIDATE, original_owner_chicago_html,
)

client = TestClient(app)

PAGE_HTML = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="robots" content="noindex,nofollow,noarchive">'
    '<style>body{background:#01091c;color:#e7f1fd}</style></head>'
    '<body><main><h1>Chicago source-backed study — controlled fixture</h1>'
    '<img src="data:image/png;base64,aGVsbG8=" alt="fixture"/></main></body></html>'
)


@pytest.fixture
def staged_approvals(tmp_path):
    def write_json(name, record):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))
        return path
    original_manifest = tmp_path / "runtime/astra/owned_campaign_deployed_release.json"
    original_manifest.parent.mkdir(parents=True)
    # Fixture SHA substitutes ONLY for the additive receipt readback; the
    # actual five live campaign HTML remains served by the true original.
    original_manifest.write_text('{"fixture_only":"original_five"}')
    five_digest = hashlib.sha256(original_manifest.read_bytes()).hexdigest()
    deployed_digest = hashlib.sha256(PAGE_HTML.encode()).hexdigest()
    html_path = tmp_path / "apps/empire-public-site/out/research" / f"{CAMPAIGN_ID}.html"
    html_path.parent.mkdir(parents=True)
    html_path.write_text(PAGE_HTML)
    receipt = {
        "schema_version": SCHEMA,
        "candidate_id": CANDIDATE,
        "campaign_id": CAMPAIGN_ID,
        "source_preview_sha256": ORIGINAL_PREVIEW_SHA,
        "deployed_html_sha256": deployed_digest,
        "original_five_release_sha256": five_digest,
        "zero_paid_media": True,
        "indexation_enabled": False,
        "lead_form_enabled": False,
        "outbound_authorized": False,
        "execution_authority": "none",
        "site_owner_live_readback_verified": True,
        "original_site_owner_release_approved": True,
        "url": f"https://empire-ai.co.uk/research/{CAMPAIGN_ID}",
    }
    release = write_json("runtime/public_website/one_chicago_research_release.json", receipt)
    approvals = {}
    for role in ("seo", "brand", "website"):
        record = {
            "schema_version": APPROVAL_SCHEMA,
            "review_lane": role,
            "independently_approved": True,
            "owner_ref": f"synthetic-fixture-{role}-not-a-real-approval",
            "candidate_id": CANDIDATE,
            "source_preview_sha256": ORIGINAL_PREVIEW_SHA,
            "deployed_html_sha256": deployed_digest,
            "approval_scope": "single_chicago_citywide_research",
        }
        approvals[role] = write_json(
            f"runtime/public_website/approvals/chicago_research_{role}.json", record)
    return {"root": tmp_path, "receipt": release, "approvals": approvals}


def _mock_owner_fallback(monkeypatch, fixture_root):
    original_release = original.released_html  # capture unmodified function
    def patched(campaign_id, root=original.ROOT):
        existing = original_release(campaign_id, root)
        if existing is not None:
            return existing
        return original_owner_chicago_html(
            campaign_id, root=fixture_root,
            existing_release_reader=lambda unused: original.load_release(root),
            existing_paths_reader=lambda unused: original.released_paths(root),
        )
    monkeypatch.setattr(original, "released_html", patched)


def test_real_gateway_keeps_all_original_five_live_routes():
    paths = original.released_paths()
    assert len(paths) == 5
    for route in paths:
        result = client.get(route)
        assert result.status_code == 200
        assert result.headers.get("cache-control") == "no-store"
        assert "<html" in result.text.casefold()


def test_real_gateway_denies_chicago_get_head_without_owner_receipts():
    for method in ("get", "head"):
        result = getattr(client, method)(f"/research/{CAMPAIGN_ID}")
        assert result.status_code == 404
        assert result.headers.get("cache-control") == "no-store"


def test_real_gateway_owner_review_fallback_stays_denied_without_evidence(
    monkeypatch, tmp_path,
):
    _mock_owner_fallback(monkeypatch, tmp_path)
    assert client.get(f"/research/{CAMPAIGN_ID}").status_code == 404
    assert client.head(f"/research/{CAMPAIGN_ID}").status_code == 404
    assert len(original.released_paths()) == 5


@pytest.mark.parametrize("method", ["get", "head"])
def test_real_gateway_synthetic_approval_fixture_reads_single_reviewed_page(
    staged_approvals, monkeypatch, method,
):
    """Positive acceptance test, not a permission to deploy this fixture."""
    _mock_owner_fallback(monkeypatch, staged_approvals["root"])
    result = getattr(client, method)(f"/research/{CAMPAIGN_ID}")
    assert result.status_code == 200
    assert result.headers.get("cache-control") == "no-store"
    assert "img-src 'self' data:" in result.headers["content-security-policy"]
    if method == "get":
        assert result.text == PAGE_HTML
        assert "noindex,nofollow,noarchive" in result.text
    else:
        assert result.content == b""
    assert len(original.released_paths()) == 5


@pytest.mark.parametrize("approval", ["seo", "brand", "website"])
def test_real_gateway_missing_any_approval_is_404(
    staged_approvals, monkeypatch, approval,
):
    staged_approvals["approvals"][approval].unlink()
    _mock_owner_fallback(monkeypatch, staged_approvals["root"])
    assert client.get(f"/research/{CAMPAIGN_ID}").status_code == 404


def test_real_gateway_does_not_expose_other_campaign_through_addendum(
    staged_approvals, monkeypatch,
):
    _mock_owner_fallback(monkeypatch, staged_approvals["root"])
    assert client.get("/research/campaign_" + "0"*24).status_code == 404
    assert all(client.get(path).status_code == 200 for path in original.released_paths())


def test_chicago_unreleased_page_is_absent_from_public_sitemap():
    xml = client.get("/sitemap.xml")
    assert xml.status_code == 200
    assert f"/research/{CAMPAIGN_ID}" not in xml.text


def test_original_gateway_denial_has_security_headers_and_no_cache():
    response = client.get(f"/research/{CAMPAIGN_ID}")
    assert response.status_code == 404
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
