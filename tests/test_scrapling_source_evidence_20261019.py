"""Offline Scrapling source-evidence bridge tests; no network or DB."""
from datetime import datetime, timezone

import pytest

from empire_os.scrapling_source_evidence import (
    EvidenceSourceHold, ReviewedRecipe, ScraplingNotInstalled,
    extract_reviewed_page,
)


class Match:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Row:
    def __init__(self, data):
        self.data = data

    def css(self, css):
        return Match(self.data.get(css, ""))


class Page:
    def __init__(self, records):
        self.records = records

    def css(self, css):
        assert css == ".business"
        return (Row(record) for record in self.records)


RECORDS = [
    {".name::text": "Acme Solar Ltd", "a::attr(href)": "/company/acme",
     ".phone::text": "01234 111222"},
    {".name::text": "Acme Solar Ltd", "a::attr(href)": "/company/acme",
     ".phone::text": "01234 111222"},
    {".name::text": "Green Light Energy", "a::attr(href)": "javascript:alert(1)",
     ".phone::text": ""},
]


def recipe(**overrides):
    args = dict(
        source_id="gb_recc_solar",
        source_url="https://www.recc.org.uk/scheme/members",
        niche="solar",
        metro="London",
        row_css=".business",
        name_css=".name::text",
        website_css="a::attr(href)",
        field_phone_css=".phone::text",
        max_rows=10,
        terms_reviewed=True,
        robots_reviewed=True,
        privacy_reviewed=True,
        review_evidence_refs=("terms:fixture", "robots:fixture", "privacy:fixture"),
    )
    args.update(overrides)
    return ReviewedRecipe(**args)


def propose(config=None, rows=RECORDS):
    return extract_reviewed_page(
        recipe=config or recipe(),
        html="<html><body>public directory fixture</body></html>",
        observed_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        selector_factory=lambda html, url: Page(rows),
    )


def test_offline_evidence_never_invents_inventory_or_consent():
    report = propose()
    assert report["records_observed"] == 2
    assert report["rows_inspected_bounded"] == 3
    assert report["canonical_empiredb_writes"] is False
    assert report["sellable_inventory_verified"] is False
    assert report["buyer_intent_verified"] is False
    assert report["outbound_sent"] is False
    assert report["live_network_access"] is False
    assert report["source_raw_resale_policy"] is False
    assert report["records"][0]["source_link_observed"] == (
        "https://www.recc.org.uk/company/acme"
    )
    assert report["records"][1]["source_link_observed"] == ""
    assert report["records"][0]["canonical_prospect_id"] is None


@pytest.mark.parametrize("overrides,reason", [
    ({"source_id": "unknown"}, "source_not_registered"),
    ({"source_url": "http://www.recc.org.uk/scheme/members"}, "unsafe_url"),
    ({"source_url": "https://127.0.0.1/scheme/members"}, "ip_literal_disallowed"),
    ({"source_url": "https://www.recc.org.uk:bad/scheme/members"}, "unsafe_url"),
    ({"source_url": "https://wrong.example.com/scheme/members"}, "url_not_in_registered_source_host"),
    ({"terms_reviewed": False}, "governance_review_missing"),
    ({"privacy_reviewed": False}, "governance_review_missing"),
    ({"review_evidence_refs": ()}, "review_evidence_refs_missing"),
    ({"robots_reviewed": False}, "governance_review_missing"),
    ({"max_rows": 26}, "unbounded_extraction"),
    ({"max_rows": True}, "unbounded_extraction"),
])
def test_policy_fails_closed(overrides, reason):
    with pytest.raises(EvidenceSourceHold, match=reason):
        propose(recipe(**overrides))


def test_raw_page_budget_and_dedupe_distinct():
    report = propose(recipe(max_rows=2))
    assert report["rows_inspected_bounded"] == 2
    assert report["records_observed"] == 1
    assert report["bounded_by_recipe"] is True


def test_no_inferred_lead_on_empty_data():
    report = propose(rows=[{".name::text": ""}])
    assert report["records_observed"] == 0


def test_unverified_timestamp_fails_closed():
    with pytest.raises(EvidenceSourceHold, match="timestamp_not_timezone_aware"):
        extract_reviewed_page(
            recipe=recipe(),
            html="<html>fixture</html>",
            observed_at=datetime(2026, 10, 19),
            selector_factory=lambda html, url: Page(RECORDS),
        )


def test_no_paid_or_browser_fetcher_used():
    # Tests provide a selector factory, not any network fetcher or live client.
    report = propose()
    assert report["mode"] == "OFFLINE_REVIEW_ONLY"
    assert all(row["data_use"] == "internal_acquisition" for row in report["records"])


def test_real_scrapling_offline_fixture_if_dependency_installed():
    """Exercise the actual optional parser only when available, without HTTP."""
    pytest.importorskip("scrapling")
    html = """<html><body>
      <article class="business"><span class="name">Acme Solar Ltd</span>
      <a href="/company/acme">Company</a><span class="phone">01234 111222</span></article>
      <article class="business"><span class="name">Green Light Energy</span>
      <a href="javascript:alert(1)">Link</a></article>
    </body></html>"""
    report = extract_reviewed_page(
        recipe=recipe(),
        html=html,
        observed_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
    )
    assert report["records_observed"] == 2
    assert report["records"][0]["business_name"] == "Acme Solar Ltd"
    assert report["records"][0]["source_link_observed"] == (
        "https://www.recc.org.uk/company/acme"
    )
    assert report["records"][0]["business_website_verified"] is False
    assert report["records"][1]["source_link_observed"] == ""
