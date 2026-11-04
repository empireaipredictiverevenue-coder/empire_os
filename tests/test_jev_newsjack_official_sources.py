"""Official first-party source tests — network disabled and callbacks injected."""
from datetime import datetime, timezone
import pytest

from empire_os.jev_newsjack_official_sources import (
    _receive_official_json, SourceUnavailable,
    federal_register_signals, govuk_primary_signal,
)
from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic


AS_OF = "2026-10-18T12:00:00+00:00"
FR_URL = "https://www.federalregister.gov/documents/2026/10/16/2026-21190/solar-installations"
GOV_URL = "https://www.gov.uk/guidance/approved-document-l-energy-and-greenhouse-gas-emissions-frequently-asked-questions"


def us_payload():
    return {"results": [
        {"document_number": "2026-21190", "title": "Solar Installation Technical Standards",
         "html_url": FR_URL, "publication_date": "2026-10-16", "type": "Rule"},
        {"document_number": "2026-21282", "title": "Solar Incentives for Utilities",
         "html_url": "https://www.federalregister.gov/documents/2026/10/19/2026-21282/solar-incentives",
         "publication_date": "2026-10-19", "type": "Notice"},
        {"document_number": "2026-21100", "title": "Combined Notice of Filings #1",
         "html_url": "https://www.federalregister.gov/documents/2026/10/16/2026-21100/combined",
         "publication_date": "2026-10-16", "type": "Notice"},
    ]}


def uk_payload():
    return {
        "base_path": "/guidance/approved-document-l-energy-and-greenhouse-gas-emissions-frequently-asked-questions",
        "title": "Approved Document L: Energy and greenhouse gas emissions, frequently asked questions",
        "content_id": "fixture:doc",
        "first_published_at": "2026-09-08T12:00:00+01:00",
        "public_updated_at": "2026-09-29T10:59:37+01:00",
        "document_type": "detailed_guide",
    }


def test_us_date_precision_and_future_schedule_kept_separate():
    data = federal_register_signals(
        term="solar", as_of=AS_OF, sector="solar",
        fetch_json=lambda url: us_payload(), max_results=3,
    )
    assert data["generic_or_off_topic_filtered"] == 1
    assert len(data["signals"]) == 2
    first = data["signals"][0]
    assert first["publication_date_verified"] is True
    assert first["published_at"] is None
    assert first["evidence_refs"][0].startswith("federalregister:api:")
    result = review_newsjack_jev_traffic(
        data["signals"], as_of=AS_OF,
        approved_sectors=["solar"], approved_markets=["US"],
    )
    mapping = {row["publication_date"]: row for row in result["candidates"]}
    assert mapping["2026-10-16"]["status"] == "RESEARCH_REVIEW"
    assert mapping["2026-10-16"]["publication_precision"] == "day"
    assert mapping["2026-10-19"]["status"] == "HOLD_EVIDENCE"
    assert "future_or_inconsistent_timestamp" in mapping["2026-10-19"]["missing_evidence"]
    assert result["publishing_enabled"] is False
    assert result["execution_authority"] == "none"


def test_uk_first_published_not_updated_is_freshness_anchor():
    data = govuk_primary_signal(
        public_url=GOV_URL, sector="solar", as_of=AS_OF,
        fetch_json=lambda url: uk_payload(),
    )
    s = data["signals"][0]
    assert s["published_at"].startswith("2026-09-08")
    assert s["source_public_updated_at"].startswith("2026-09-29")
    result = review_newsjack_jev_traffic(
        data["signals"], as_of=AS_OF,
        approved_sectors=["solar"], approved_markets=["GB"],
    )
    assert result["candidates"][0]["status"] == "HOLD_EVIDENCE"
    assert "stale_news_signal" in result["candidates"][0]["missing_evidence"]


def test_govuk_rejects_unsafe_url_redirect_or_withdrawal():
    with pytest.raises(ValueError):
        govuk_primary_signal(
            public_url="https://internal.local/news", as_of=AS_OF,
            sector="solar", fetch_json=lambda url: uk_payload(),
        )
    with pytest.raises(ValueError):
        govuk_primary_signal(
            public_url="http://www.gov.uk/guidance/solar", as_of=AS_OF,
            sector="solar", fetch_json=lambda url: uk_payload(),
        )
    with pytest.raises(SourceUnavailable):
        govuk_primary_signal(
            public_url=GOV_URL, as_of=AS_OF, sector="solar",
            fetch_json=lambda url: {**uk_payload(), "withdrawn_notice": {"reason": "withdrawn"}},
        )


def test_official_json_url_restrictions_before_network():
    for bad_url in (
        "http://www.gov.uk/api/content/guidance/a",
        "https://www.gov.uk.evil.tld/api/content/a",
        "https://localhost/api/content/private",
        "https://www.federalregister.gov/api/v1/secrets",
    ):
        with pytest.raises(ValueError):
            _receive_official_json(bad_url)


def test_us_rejects_unbounded_queries_and_unknown_sectors():
    with pytest.raises(ValueError):
        federal_register_signals(
            term="solar", as_of=AS_OF, sector="unapproved",
            fetch_json=lambda url: us_payload(),
        )
    with pytest.raises(ValueError):
        federal_register_signals(
            term="solar/../../", as_of=AS_OF, sector="solar",
            fetch_json=lambda url: us_payload(),
        )
    with pytest.raises(ValueError):
        federal_register_signals(
            term="solar", as_of=AS_OF, sector="solar", max_results=100000,
            fetch_json=lambda url: us_payload(),
        )


def test_unexpected_response_and_fake_dates_fail_closed():
    with pytest.raises(SourceUnavailable):
        federal_register_signals(
            term="solar", as_of=AS_OF, sector="solar",
            fetch_json=lambda url: {"items": []},
        )
    data = us_payload()
    data["results"][0]["publication_date"] = "2026-10-xx"
    output = federal_register_signals(
        term="solar", as_of=AS_OF, sector="solar",
        fetch_json=lambda url: data,
    )
    assert all(s["publication_date"] != "2026-10-xx" for s in output["signals"])


def test_bounded_deeper_scan_finds_specific_record_after_generic_notices():
    from urllib.parse import parse_qs, urlsplit
    seen = []
    def reader(url):
        size = int(parse_qs(urlsplit(url).query)["per_page"][0])
        seen.append(size)
        assert 20 <= size <= 50
        generic = [
            {
                "document_number": f"2026-{10001 + i}",
                "title": "Combined Notice of Filings",
                "html_url": (
                    "https://www.federalregister.gov/documents/2026/11/04/"
                    f"2026-{10001+i}/combined-notice"
                ),
                "publication_date": "2026-11-04",
                "type": "Notice",
            }
            for i in range(17)
        ]
        specific = {
            "document_number": "2026-11099",
            "title": "Solar Installation Technical Requirements",
            "html_url":
                "https://www.federalregister.gov/documents/2026/11/03/"
                "2026-11099/solar-installation",
            "publication_date": "2026-11-03",
            "type": "Rule",
        }
        return {"results": generic + [specific]}

    result = federal_register_signals(
        term="solar", as_of="2026-11-04T14:17:00+00:00", sector="solar",
        max_results=2, fetch_json=reader,
    )
    assert result["candidate_count"] == 1
    assert result["source_records_scanned"] == 18
    assert result["generic_or_off_topic_filtered"] == 17
    assert 20 <= result["scan_limit"] <= 50
    assert result["signals"][0]["title"] == "Solar Installation Technical Requirements"
    assert result["signals"][0]["publication_date"] == "2026-11-03"
    assert seen == [result["scan_limit"]]


def test_multi_word_term_must_match_concept_not_individual_generic_word():
    samples = [
        ("2026-10110", "Super Intelligence in Operational Assessments"),
        ("2026-10111", "Artificial Intelligence Software Deployment"),
    ]
    packet = {
        "results": [{
            "document_number": number,
            "title": title,
            "html_url":
                "https://www.federalregister.gov/documents/2026/11/04/"
                + number + "/artificial-intelligence",
            "publication_date": "2026-11-04",
            "type": "Rule",
        } for number,title in samples]
    }
    result = federal_register_signals(
        term="artificial intelligence", as_of="2026-11-04T14:17:00+00:00",
        sector="ai", max_results=2, fetch_json=lambda _: packet,
    )
    assert result["candidate_count"] == 1
    assert result["signals"][0]["title"] == "Artificial Intelligence Software Deployment"
