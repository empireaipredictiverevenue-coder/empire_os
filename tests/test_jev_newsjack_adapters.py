"""Regressions for existing research / Search Console integration (all offline)."""
import pytest
from empire_os.jev_newsjack_adapters import (
    signals_from_last30days_agent_export, attach_gsc_query_page_observations,
    SearchIntelligenceLoopbackGSCReader,
)
from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic
from empire_os.search_intelligence.search_console import (
    GoogleSearchConsoleAdapter, SearchConsoleUnavailable,
)

AS_OF = "2026-10-18T12:00:00+00:00"
DEST = "https://empire-ai.co.uk/industries/solar"


def export():
    return {
        "schema_version": "1.2", "generated_at": AS_OF,
        "source_status": {"techmeme": "ok", "reddit": "partial"},
        "results": [
            {"candidate_id": "t-1", "source": "techmeme",
             "title": "New solar equipment requirements published for installers",
             "url": "https://www.techmeme.com/261017/solar",
             "published_at": "2026-10-17T10:00:00+00:00"},
            {"candidate_id": "r-2", "source": "reddit",
             "title": "Solar installation cost discussion for United Kingdom",
             "url": "https://www.reddit.com/r/solar/comments/123/example/",
             "published_at": "2026-10-17"},
        ],
    }


def fake_reader(tmp_path, *, site="sc-domain:empire-ai.co.uk", rows=None):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    def response(url, headers, payload):
        assert "searchAnalytics/query" in url
        assert payload["dimensions"] == ["query", "page"]
        assert headers["Authorization"].startswith("Bearer ")
        return {"rows": rows if rows is not None else [{
            "keys": ["solar installation UK", DEST],
            "clicks": 2, "impressions": 30,
        }]}
    return GoogleSearchConsoleAdapter(
        site, credential, token_provider=lambda p: "fixture-token",
        post_json=response,
    )


def test_maps_existing_last30days_export_without_fabrication():
    mapped = signals_from_last30days_agent_export(export(), sector="solar", market="GB")
    assert mapped["mapped_count"] == 2
    assert mapped["rejected_count"] == 0
    a, b = mapped["signals"]
    assert a["published_at"].startswith("2026-10-17T10:00")
    assert a["evidence_refs"][0].startswith("last30days:agent_export:")
    assert a["independent_corroboration_verified"] is False
    assert b["published_at"] is None
    assert b["timestamp_granularity"] == "unknown_or_date_only"
    output = review_newsjack_jev_traffic(
        mapped["signals"], as_of=AS_OF, approved_sectors=["solar"],
        approved_markets=["GB"],
    )
    assert output["status_counts"] == {"HOLD_EVIDENCE": 1, "RESEARCH_REVIEW": 1}
    assert output["execution_authority"] == "none"


def test_rejects_unknown_sources_and_unversioned_input():
    invalid = export()
    invalid["results"][0]["source"] = "invented"
    assert signals_from_last30days_agent_export(
        invalid, sector="solar", market="GB",
    )["rejected_count"] == 1
    invalid["schema_version"] = "other"
    with pytest.raises(ValueError):
        signals_from_last30days_agent_export(invalid, sector="solar", market="GB")


def test_attaches_exact_search_query_and_page_evidence(tmp_path):
    signal = signals_from_last30days_agent_export(
        export(), sector="solar", market="GB",
    )["signals"][0]
    result = attach_gsc_query_page_observations(
        [signal], reader=fake_reader(tmp_path), as_of=AS_OF,
        start_date="2026-10-10", end_date="2026-10-16",
        query_by_signal_id={signal["signal_id"]: "solar installation UK"},
        destination_by_signal_id={signal["signal_id"]: DEST},
    )
    assert result["exact_matches"] == 1
    item = result["signals"][0]
    assert item["search_observation"]["impressions"] == 30
    assert item["search_observation"]["metric_scope"] == "historical_query_page_not_news_attribution"
    assert result["news_attributed_clicks"] is None
    assert item["destination_live_verified"] is False
    assert item["search_observation"]["source_ref"].startswith("gsc:query_page:")
    reviewed = review_newsjack_jev_traffic(
        [item], as_of=AS_OF, approved_sectors=["solar"],
        approved_markets=["GB"], approved_destination_urls=[DEST],
    )["candidates"][0]
    assert reviewed["status"] == "RESEARCH_REVIEW"
    assert reviewed["search_observation"]["clicks"] == 2
    assert "verified_live_destination_required" in reviewed["missing_evidence"]


def test_no_wrong_page_or_wrong_keyword_or_external_site(tmp_path):
    signal = signals_from_last30days_agent_export(
        export(), sector="solar", market="GB",
    )["signals"][0]
    options = {
        "reader": fake_reader(tmp_path), "as_of": AS_OF,
        "start_date": "2026-10-10", "end_date": "2026-10-16",
    }
    assert attach_gsc_query_page_observations(
        [signal], **options,
        query_by_signal_id={signal["signal_id"]: "roofing insurance"},
        destination_by_signal_id={signal["signal_id"]: DEST},
    )["exact_matches"] == 0
    assert attach_gsc_query_page_observations(
        [signal], **options,
        query_by_signal_id={signal["signal_id"]: "solar installation UK"},
        destination_by_signal_id={signal["signal_id"]: "https://example.org/"},
    )["exact_matches"] == 0


def test_reader_or_window_cannot_expand_scope(tmp_path):
    signal = signals_from_last30days_agent_export(
        export(), sector="solar", market="GB",
    )["signals"][0]
    args = dict(
        signals=[signal], as_of=AS_OF,
        start_date="2026-10-10", end_date="2026-10-16",
        query_by_signal_id={}, destination_by_signal_id={},
    )
    with pytest.raises(ValueError):
        attach_gsc_query_page_observations(**args, reader=object())
    with pytest.raises(ValueError):
        attach_gsc_query_page_observations(
            **args, reader=fake_reader(tmp_path, site="sc-domain:othercompany.com"))
    with pytest.raises(ValueError):
        attach_gsc_query_page_observations(
            **{**args, "end_date": "2026-11-20"}, reader=fake_reader(tmp_path))


def test_duplicate_gsc_query_page_rows_are_dropped(tmp_path):
    signal = signals_from_last30days_agent_export(
        export(), sector="solar", market="GB",
    )["signals"][0]
    duplicates = [{"keys": ["solar installation UK", DEST],
                   "clicks": 2, "impressions": 30}] * 3
    result = attach_gsc_query_page_observations(
        [signal], reader=fake_reader(tmp_path, rows=duplicates),
        as_of=AS_OF, start_date="2026-10-10", end_date="2026-10-16",
        query_by_signal_id={signal["signal_id"]: "solar installation UK"},
        destination_by_signal_id={signal["signal_id"]: DEST},
    )
    assert result["exact_matches"] == 0


def test_no_implicit_reader_or_network_for_news_export():
    result = signals_from_last30days_agent_export(export(), sector="solar", market="GB")
    assert all("search_observation" not in s for s in result["signals"])
    assert all(s["destination_live_verified"] is False for s in result["signals"])


def test_loopback_reader_reuses_first_party_service_contract(monkeypatch):
    calls = []
    def stub(self, path, query=None):
        calls.append((path, query))
        if path.endswith("/status"):
            return {"enabled": True, "configured": True, "available": True,
                    "reason": "ready", "site_url": "sc-domain:empire-ai.co.uk"}
        return {"available": True, "source": "google_search_console",
                "site_url": "sc-domain:empire-ai.co.uk",
                "items": [{"keys": ["solar installation UK", DEST],
                           "clicks": 0, "impressions": 8}]}
    monkeypatch.setattr(SearchIntelligenceLoopbackGSCReader, "_get", stub)
    r = SearchIntelligenceLoopbackGSCReader()
    packet = signals_from_last30days_agent_export(export(), sector="solar", market="GB")
    s = packet["signals"][0]
    linked = attach_gsc_query_page_observations(
        [s], reader=r, as_of=AS_OF,
        start_date="2026-10-10", end_date="2026-10-16",
        query_by_signal_id={s["signal_id"]: "solar installation UK"},
        destination_by_signal_id={s["signal_id"]: DEST},
    )
    assert linked["exact_matches"] == 1
    assert linked["signals"][0]["search_observation"]["impressions"] == 8
    assert linked["live_destination_verified"] is False
    assert calls[0][0].endswith("/status")
    assert calls[1][0].endswith("/observations")


def test_loopback_rejects_untrusted_site_and_source(monkeypatch):
    def stub(self, path, query=None):
        if path.endswith("/status"):
            return {"enabled": True, "configured": True, "available": True,
                    "reason": "ready", "site_url": "sc-domain:otherco.com"}
        return {"available": True, "source": "unsupported_source",
                "site_url": "sc-domain:empire-ai.co.uk", "items": []}
    monkeypatch.setattr(SearchIntelligenceLoopbackGSCReader, "_get", stub)
    with pytest.raises(SearchConsoleUnavailable):
        SearchIntelligenceLoopbackGSCReader().status()
