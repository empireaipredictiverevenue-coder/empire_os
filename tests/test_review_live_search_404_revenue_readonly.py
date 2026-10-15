"""Actual GSC observations versus permitted same-origin HTTP statuses, no writes."""
from __future__ import annotations

from datetime import date, timedelta
import json

import pytest

from scripts import review_live_search_404_revenue_readonly as audit

NOW = date.today()
END = NOW - timedelta(days=2)
START = END - timedelta(days=12)


def daily(rows=None):
    if rows is None:
        rows = [{
            "keys": [START.isoformat()],
            "impressions": 30, "clicks": 1,
        }]
    return {
        "source": "google_search_console",
        "site_url": audit.SITE,
        "available": True,
        "count": len(rows),
        "items": rows,
    }


def query_rows(rows=None):
    if rows is None:
        rows = [
            {"keys": ["how do i know ready buyers", "https://empire-ai.co.uk/aeo/accounting/TAM/"],
             "impressions": 4, "clicks": 0},
            {"keys": ["off-topic", "https://empire-ai.co.uk/aeo/antenna-install/EUG/"],
             "impressions": 3, "clicks": 0},
            {"keys": ["brand", "https://empire-ai.co.uk/"], "impressions": 8, "clicks": 1},
        ]
    return {
        "source": "google_search_console",
        "site_url": audit.SITE,
        "available": True,
        "count": len(rows),
        "items": rows,
    }


def test_real_page_and_tam_topic_prioritized_but_not_published():
    called = []
    def probe(path):
        called.append(path)
        return 404
    result = audit.audit(daily(), query_rows(), origin_status=probe,
                         start=START, end=END)
    assert result["status"] == "OBSERVED_404_REVIEW_QUEUE"
    assert result["broken_paths_found"] == 2
    assert result["broken_disclosed_impressions"] == 7
    assert result["sitewide_observed_impressions"] == 30
    assert result["sitewide_observed_clicks"] == 1
    assert result["query_page_coverage_complete"] is False
    assert result["organic_conversion_attributed"] is False
    assert result["search_terms_disclosed"] is False
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False
    assert result["redirect_authorized"] is False
    assert result["publishing_authorized"] is False
    assert result["known_revenue_topic_review_count"] == 1
    first = result["broken_review_queue"][0]
    assert first["path"] == "/aeo/accounting/TAM/"
    assert first["product_relevance"] == "BUYER_INTENT_TAM_RESEARCH"
    assert first["next_action"] == "REVIEW_FIRST_PARTY_BUYER_INTENT_EVIDENCE_AND_EXACT_PAGE_CONTENT"
    assert "/aeo/antenna-install/EUG/" in called
    assert "/" not in called
    assert "how do i know ready buyers" not in json.dumps(result)


def test_live_200_remains_no_fake_broken_page():
    result = audit.audit(daily(), query_rows(), origin_status=lambda _: 200,
                         start=START, end=END)
    assert result["status"] == "NO_BROKEN_URLS_IN_DISCLOSED_SAMPLE"
    assert result["broken_review_queue"] == []
    assert result["allowed_paths_probed"] == 2


@pytest.mark.parametrize("url", [
    "http://empire-ai.co.uk/aeo/accounting/TAM/",
    "https://www.empire-ai.co.uk/aeo/accounting/TAM/",
    "https://empire-ai.co.uk@127.0.0.1/aeo/accounting/TAM/",
    "https://empire-ai.co.uk:9001/aeo/accounting/TAM/",
    "https://empire-ai.co.uk/aeo/accounting/TAM/?email=secret",
    "https://empire-ai.co.uk/%2e%2e/hidden",
    "https://empire-ai.co.uk/manager",
    "https://example.org/aeo/accounting/TAM/",
    "file:///etc/empire.env",
    "",
])
def test_external_private_or_untrusted_page_urls_are_never_probed(url):
    rows = query_rows([{"keys": ["sensitive string hidden", url],
                        "impressions": 5, "clicks": 0}])
    called = []
    report = audit.audit(daily(), rows, origin_status=lambda p: called.append(p) or 404,
                         start=START, end=END)
    assert called == []
    assert report["excluded_query_page_rows"] == 1
    assert report["broken_paths_found"] == 0
    assert "sensitive string hidden" not in json.dumps(report)


@pytest.mark.parametrize("field,value", [
    ("available", False),
    ("source", "synthetic"),
    ("site_url", "sc-domain:some-other-site.org"),
    ("count", 9999),
    ("items", {"not": "rows"}),
])
def test_gsc_must_match_exact_provider_envelope(field, value):
    with pytest.raises(audit.ReviewHeld):
        audit.audit({**daily(), field: value}, query_rows(),
                    origin_status=lambda _: 200, start=START, end=END)


@pytest.mark.parametrize("row", [
    {"keys": ["private", "https://empire-ai.co.uk/aeo/accounting/TAM/"],
     "impressions": True, "clicks": 0},
    {"keys": ["private", "https://empire-ai.co.uk/aeo/accounting/TAM/"],
     "impressions": -1, "clicks": 0},
    {"keys": ["private", "https://empire-ai.co.uk/aeo/accounting/TAM/"],
     "impressions": 1, "clicks": 2},
    {"keys": ["not-two-values"], "impressions": 1, "clicks": 0},
])
def test_query_page_data_cannot_fake_metrics(row):
    with pytest.raises(audit.ReviewHeld):
        audit.audit(daily(), query_rows([row]), origin_status=lambda _: 200,
                    start=START, end=END)


@pytest.mark.parametrize("shift_days", [0, 2, 32])
def test_current_or_oversize_windows_fail_closed(shift_days):
    if shift_days == 0:
        a, b = NOW, NOW
    elif shift_days == 2:
        a, b = NOW, NOW - timedelta(days=1)
    else:
        a, b = NOW - timedelta(days=34), NOW - timedelta(days=2)
    with pytest.raises(audit.ReviewHeld):
        audit.audit(daily(), query_rows(), origin_status=lambda _: 200,
                    start=a, end=b)


def test_date_reuse_fails_closed():
    d = daily([{"keys":[START.isoformat()],"impressions":1,"clicks":0},
               {"keys":[START.isoformat()],"impressions":1,"clicks":0}])
    with pytest.raises(audit.ReviewHeld):
        audit.audit(d, query_rows(), origin_status=lambda _:200,start=START,end=END)


def test_redirect_proposal_is_not_automatically_authorized():
    out = audit.audit(daily(), query_rows(), origin_status=lambda _:301,
                      start=START, end=END)
    assert out["broken_paths_found"] == 0
    assert out["publishing_authorized"] is False
    assert out["redirect_authorized"] is False


def test_unverified_origin_status_never_claims_recovery():
    with pytest.raises(audit.ReviewHeld, match="ORIGIN_HTTP_PROBE_UNVERIFIED"):
        audit.audit(daily(),query_rows(),origin_status=lambda _:202,
                    start=START,end=END)


def test_source_unavailable_never_falls_back_to_mock_counts(monkeypatch):
    monkeypatch.setattr(audit, "_json_get", lambda p: (
        (_ for _ in ()).throw(audit.ReviewHeld("GSC_SOURCE_UNAVAILABLE"))
    ))
    report = audit.run(today=NOW)
    assert report["status"] == "HELD"
    assert report["database_writes"] is False
    assert report["publishing_authorized"] is False


def test_local_http_transport_get_only_and_no_redirect(monkeypatch):
    seen=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self, cap):return b"ok"
    class Opener:
        def open(self, req, timeout):
            seen.append((req.get_method(), req.full_url, timeout))
            return Response()
    monkeypatch.setattr(audit, "build_opener", lambda *a: Opener())
    status,payload=audit._get("/aeo/accounting/TAM/",search=False)
    assert status==200 and payload==b"ok"
    assert seen==[("GET", "http://127.0.0.1/aeo/accounting/TAM/", 12)]
    with pytest.raises(audit.ReviewHeld):
        audit._get("/../../secret", search=False)


def test_no_raw_search_terms_in_report_even_with_pii_like_query():
    rows=query_rows([{"keys": ["person@example.org", "https://empire-ai.co.uk/aeo/accounting/TAM/"],
                      "impressions":1,"clicks":0}])
    result=audit.audit(daily(),rows,origin_status=lambda _:404,
                       start=START,end=END)
    assert "person@example.org" not in json.dumps(result)
    assert "BUYER_INTENT_TAM_RESEARCH" in json.dumps(result)
