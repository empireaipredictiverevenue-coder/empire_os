from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.search_intelligence.search_console import (
    GoogleSearchConsoleAdapter, SearchConsoleUnavailable,
)
from empire_os.search_intelligence.owned_url_inspection import (
    URLS, SITE, INSPECTION_ENDPOINT, parse_inspection, inspect_fixed_urls,
)
from scripts.inspect_owned_gsc_indexed_version_readonly import write_private_once


def fake_adapter(tmp_path, response=None, *, property=SITE):
    credential = tmp_path / "credential.json"
    credential.write_text("{}")
    calls = []
    def provider(path: Path):
        assert path == credential
        return "test-token"
    def sender(url, headers, payload):
        calls.append((url, headers, payload))
        return response if response is not None else {
            "inspectionResult": {"inspectionResultLink": "secret-inspection-link",
            "indexStatusResult": {
                "verdict": "PASS",
                "coverageState": "Submitted and indexed",
                "pageFetchState": "SUCCESSFUL",
                "lastCrawlTime": "2026-10-15T09:00:00Z",
                "googleCanonical": payload["inspectionUrl"],
                "userCanonical": payload["inspectionUrl"],
                "referringUrls": ["https://random.example/secret?a=foo"],
                "sitemap": ["https://empire-ai.co.uk/sitemap.xml"],
            }}
        }
    adapter = GoogleSearchConsoleAdapter(
        property, credential, token_provider=provider, post_json=sender,
    )
    return adapter, calls


def test_fixed_inspection_calls_five_owned_urls_only(tmp_path):
    adapter, calls = fake_adapter(tmp_path)
    packet = inspect_fixed_urls(
        adapter, now=lambda: datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
    )
    assert packet["count"] == 5
    assert packet["status"] == "INDEXED_VERSION_INSPECTION_RECORDED"
    assert [c[2]["inspectionUrl"] for c in calls] == list(URLS)
    assert all(c[0] == INSPECTION_ENDPOINT and c[2]["siteUrl"] == SITE for c in calls)
    assert all(c[1]["Authorization"] == "Bearer test-token" for c in calls)
    assert packet["items"][0]["coverageState"] == "Submitted and indexed"
    assert packet["google_indexing_request_sent"] is False
    assert packet["google_live_test_performed"] is False
    assert packet["full_site_indexation_verified"] is False
    assert packet["website_changed"] is False


def test_report_does_not_echo_sensitive_or_extra_source_fields(tmp_path):
    adapter, _ = fake_adapter(tmp_path)
    packet = inspect_fixed_urls(adapter)
    view = str(packet)
    assert "test-token" not in view
    assert "secret-inspection-link" not in view
    assert "random.example" not in view
    assert "sitemap.xml" not in view


@pytest.mark.parametrize("url", (
    "https://evil.example/",
    "http://empire-ai.co.uk/",
    "https://www.empire-ai.co.uk/",
    "https://empire-ai.co.uk/unsafe",
    "https://empire-ai.co.uk/commercial?code=secret",
))
def test_only_five_exact_owned_urls(url):
    with pytest.raises(SearchConsoleUnavailable, match="out_of_scope"):
        parse_inspection(url, {"inspectionResult": {"indexStatusResult": {}}})


@pytest.mark.parametrize("body", (
    {}, {"inspectionResult": {}}, {"inspectionResult": {"indexStatusResult": []}},
))
def test_fail_closed_on_missing_google_inspection_fields(body):
    with pytest.raises(SearchConsoleUnavailable):
        parse_inspection(URLS[0], body)


def test_reject_mismatched_property_before_auth(tmp_path):
    adapter, calls = fake_adapter(tmp_path, property="sc-domain:other.test")
    with pytest.raises(SearchConsoleUnavailable, match="property"):
        inspect_fixed_urls(adapter)
    assert calls == []


def test_reject_naive_clock(tmp_path):
    adapter, calls = fake_adapter(tmp_path)
    with pytest.raises(SearchConsoleUnavailable, match="clock"):
        inspect_fixed_urls(adapter, now=lambda: datetime(2026, 10, 16))
    assert calls == []


def test_other_domain_canonical_not_rebroadcast():
    packet = {"inspectionResult": {"indexStatusResult": {
        "verdict": "NEUTRAL",
        "googleCanonical": "https://other.test/id?secret=42",
        "userCanonical": "https://www.empire-ai.co.uk/different"
    }}}
    result = parse_inspection(URLS[0], packet)
    assert result["googleCanonical"] == "EXTERNAL_OR_UNVERIFIED"
    assert result["userCanonical"] == "SAME_PROPERTY_OTHER_PATH"


def test_untrusted_free_text_omitted():
    result = parse_inspection(URLS[0], {"inspectionResult": {"indexStatusResult": {
        "coverageState": "A" * 2000,
        "lastCrawlTime": "../../etc/passwd",
        "pageFetchState": ["SUCCESSFUL"],
    }}})
    assert result["coverageState"] is None
    assert result["lastCrawlTime"] is None
    assert result["pageFetchState"] is None


def test_private_receipt_once_and_not_overwrite(tmp_path):
    p = tmp_path / "empire_gsc_index_inspection_20261016.json"
    write_private_once({"status": "safe"}, p, root=tmp_path)
    assert p.read_text().find('"safe"') > 0
    assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private_once({"status": "second"}, p, root=tmp_path)


@pytest.mark.parametrize("filename", ("bad.json", "empire_gsc_index_inspection_2026.json"))
def test_reject_unapproved_report_name(tmp_path, filename):
    with pytest.raises(ValueError, match="private_report"):
        write_private_once({}, tmp_path / filename, root=tmp_path)


def test_reject_symlink_output(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("original")
    link = tmp_path / "empire_gsc_index_inspection_20261016.json"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="private_report"):
        write_private_once({}, link, root=tmp_path)
    assert outside.read_text() == "original"
