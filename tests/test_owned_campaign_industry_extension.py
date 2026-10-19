"""Approved sidecar contract and guarded extension of existing owned collector.

No live DB, real user data, source issuance, campaign publication or release
file in the repository. All I/O uses tmp_path and fake repository.
"""
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest
from starlette.requests import Request

from empire_os.owned_campaign_industry_extension import (
    RELEASE, SCHEMA, load_industry_release, validate_industry_event,
)

NOW = datetime(2026, 10, 18, 15, tzinfo=timezone.utc)
CID = "campaign_" + "a" * 24
LEGACY = {"campaigns": [{"campaign_id": "campaign_" + str(i) * 24}
                        for i in range(1, 6)]}


def staged_release(root):
    from empire_os.owned_campaign_preflight import digest
    site = root / "apps/empire-public-site/out/industries/solar.html"
    site.parent.mkdir(parents=True, exist_ok=True)
    site.write_text("<h1>First party industry research</h1>")
    item = {
        "schema_version": SCHEMA,
        "status": "OWNER_APPROVED_DEPLOYED_MEASUREMENT_ONLY",
        "execution_authority": "measurement_only",
        "zero_paid_spend": True,
        "automatic_publication": False,
        "automatic_outbound": False,
        "payments_enabled": False,
        "deployment_evidence_ref": "test-only-preview-build-receipt",
        "research_release_sha256": digest(LEGACY["campaigns"]),
        "reviews": {key: {"status": "APPROVED", "evidence_ref": "test-only-owner-review"}
                    for key in ("privacy", "website", "collector", "founder")},
        "campaigns": [{
            "campaign_id": CID,
            "asset_id": CID + ":landing",
            "landing_path": "/industries/solar",
            "sector": "solar",
            "html_sha256": sha256(site.read_bytes()).hexdigest(),
            "source_evidence_ref": "govuk:content-api:test-only",
        }],
    }
    release_file = root / RELEASE
    release_file.parent.mkdir(parents=True, exist_ok=True)
    release_file.write_text(json.dumps(item))
    return item, site, release_file


def payload(**overrides):
    return {
        "event_id": str(uuid4()),
        "event_type": "campaign_page_view",
        "campaign_id": CID, "asset_id": CID + ":landing",
        "source": "owned_site", "channel": "organic",
        "occurred_at": NOW.isoformat(),
    } | overrides


def test_no_approval_file_returns_no_release(tmp_path):
    assert load_industry_release(tmp_path, research_release=LEGACY) is None


def test_validated_sidecar_reuses_existing_landing_asset(tmp_path):
    approved, _, _ = staged_release(tmp_path)
    assert load_industry_release(tmp_path, research_release=LEGACY) == approved
    event = validate_industry_event(payload(), approved, now=NOW)
    assert set(event) == {
        "event_id", "event_type", "campaign_id", "asset_id",
        "source", "channel", "occurred_at",
    }
    assert event["asset_id"] == CID + ":landing"
    assert event["source"] == "owned_site"


@pytest.mark.parametrize("modification", [
    lambda x: x.update(status="DRAFT"),
    lambda x: x.update(execution_authority="publish"),
    lambda x: x.update(zero_paid_spend=False),
    lambda x: x.update(automatic_outbound=True),
    lambda x: x.update(payments_enabled=True),
    lambda x: x["reviews"]["privacy"].update(status="PENDING"),
    lambda x: x["reviews"]["collector"].update(evidence_ref=""),
    lambda x: x.update(research_release_sha256="b" * 64),
    lambda x: x["campaigns"][0].update(asset_id=CID + ":youtube"),
    lambda x: x["campaigns"][0].update(landing_path="/account"),
    lambda x: x["campaigns"][0].update(html_sha256="b" * 64),
    lambda x: x["campaigns"][0].update(source_evidence_ref=""),
])
def test_unapproved_invalid_releases_cannot_record_events(tmp_path, modification):
    draft, _, file = staged_release(tmp_path)
    modification(draft)
    file.write_text(json.dumps(draft))
    assert load_industry_release(tmp_path, research_release=LEGACY) is None


def test_changed_site_or_legacy_research_release_invalidates_sidecar(tmp_path):
    _, site, _ = staged_release(tmp_path)
    assert load_industry_release(tmp_path, research_release=LEGACY)
    site.write_text("modified after approval")
    assert load_industry_release(tmp_path, research_release=LEGACY) is None
    staged_release(tmp_path)
    incompatible = {"campaigns": LEGACY["campaigns"] + [{"campaign_id": "test"}]}
    assert load_industry_release(tmp_path, research_release=incompatible) is None


@pytest.mark.parametrize("patch", [
    {"event_type": "campaign_enquiry_submitted"},
    {"event_type": "purchase"},
    {"asset_id": CID + ":linkedin"},
    {"source": "youtube"},
    {"channel": "paid"},
    {"campaign_id": "campaign_" + "b" * 24},
    {"session_id": str(uuid4())},
    {"email": "buyer@example.test"},
    {"event_id": "not-a-uuid"},
    {"occurred_at": "2021-01-01T00:00:00+00:00"},
])
def test_browser_cannot_forge_attribution_identity_or_revenue(tmp_path, patch):
    approved, _, _ = staged_release(tmp_path)
    with pytest.raises(ValueError):
        validate_industry_event(payload(**patch), approved, now=NOW)


def request(row, origin="https://empire-ai.co.uk", referer=None):
    data = json.dumps(row).encode()
    async def receive():
        return {"type": "http.request", "body": data, "more_body": False}
    if referer is None:
        referer = ("https://empire-ai.co.uk/industries/solar?"
                   + "utm_campaign=" + CID + "&utm_content=" + CID
                   + "%3Alinkedin&utm_source=linkedin&utm_medium=organic_social")
    return Request({
        "type": "http", "method": "POST", "path": "/api/industry/event",
        "headers": [(b"origin", origin.encode()), (b"content-type", b"application/json"),
                    (b"referer", referer.encode())],
        "client": ("127.0.0.1", 1),
    }, receive)


def test_same_gateway_reuses_existing_repository_and_fails_closed(monkeypatch, tmp_path):
    import empire_os.owned_campaign_http as http
    import empire_os.owned_campaign_industry_extension as ext
    from empire_os.data_backends.owned_campaign_repository import OwnedCampaignRepository

    approved, _, _ = staged_release(tmp_path)
    monkeypatch.setattr(http, "LIMITER", http.IntakeLimiter())
    async def direct(fn, *args):
        return fn(*args)
    monkeypatch.setattr(http, "run_in_threadpool", direct)
    monkeypatch.setattr(http, "load_release", lambda: LEGACY)
    active = False
    monkeypatch.setattr(ext, "load_industry_release",
                        lambda **kw: approved if active else None)

    saved = []
    class FakeRepository:
        def event(self, normalized):
            saved.append(normalized)
            return normalized["event_id"]
    monkeypatch.setattr(OwnedCampaignRepository, "from_environment",
                        lambda: FakeRepository())
    assert asyncio.run(http.handle_intake(request(payload()), "industry_event")).status_code == 503
    assert not saved
    active = True
    assert asyncio.run(http.handle_intake(request(payload(), "https://evil.test"), "industry_event")).status_code == 403
    assert not saved
    accepted = asyncio.run(http.handle_intake(request(payload()), "industry_event"))
    assert accepted.status_code == 202
    assert len(saved) == 1
    assert saved[0]["asset_id"] == CID + ":landing"
    assert "session_id" not in saved[0]
    denied = asyncio.run(http.handle_intake(
        request(payload(event_type="campaign_enquiry_submitted")), "industry_event"))
    assert denied.status_code == 422 and len(saved) == 1


@pytest.mark.parametrize("browser_referrer", [
    "https://evil.test/industries/solar?utm_campaign=" + CID,
    "https://empire-ai.co.uk/industries/roofing?utm_campaign=" + CID,
    "https://empire-ai.co.uk/commercial?utm_campaign=" + CID,
    "https://empire-ai.co.uk/industries/solar?utm_campaign=" + CID,
    "https://empire-ai.co.uk/industries/solar?utm_campaign=" + CID
      + "&utm_content=" + CID + ":linkedin&utm_source=linkedin&utm_medium=paid",
    "https://empire-ai.co.uk/industries/solar?utm_campaign=" + CID
      + "&utm_content=" + CID + ":linkedin&utm_source=linkedin&utm_medium=organic_social&utm_id=yt-test",
])
def test_referrer_must_match_released_first_party_page_and_utm(tmp_path, browser_referrer):
    from empire_os.owned_campaign_industry_extension import validate_industry_referrer
    approved, _, _ = staged_release(tmp_path)
    with pytest.raises(ValueError):
        validate_industry_referrer(browser_referrer, payload(), approved)
