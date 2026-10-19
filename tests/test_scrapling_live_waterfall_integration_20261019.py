"""Real optional Scrapling parser feeding canonical SiteCrawler and Waterfall.

No outbound HTTP, DB, runtime activation, mail, customer data or browser.
"""
from datetime import datetime, timezone

import pytest

from empire_os.scrapling_contact_extractor import (
    ScraplingBusinessContactExtractor, ScraplingExtractionHeld,
    ScraplingParserUnavailable,
)
from empire_os.site_crawler import SiteCrawler
from empire_os.scrapling_source_evidence import ReviewedRecipe, extract_reviewed_page
from empire_os.scrapling_waterfall_provider import (
    ReviewedScraplingSiteProvider, build_reviewed_scrapling_waterfall,
)
from empire_os.waterfall import LeadContact, build_default_waterfall
from empire_os.waterfall_source_bridge import EvidenceReview


NOW = datetime(2026, 10, 19, 11, 30, tzinfo=timezone.utc)
HTML = """<html><head><title>Test Solar Company</title></head><body>
    <a href="mailto:office@solar-firm.example">Office</a>
    <a href="tel:+442079460001">Phone</a>
    <main><p>For projects please email contact@solar-firm.example.</p></main>
    <script>secrets@should-not-extract.example</script>
    </body></html>"""


def source_report():
    return extract_reviewed_page(
        recipe=ReviewedRecipe(
            source_id="gb_recc_solar",
            source_url="https://www.recc.org.uk/scheme/members",
            niche="solar", metro="London",
            row_css="article.company", name_css=".name::text",
            website_css="a::attr(href)", max_rows=3,
            terms_reviewed=True, robots_reviewed=True,
            privacy_reviewed=True,
            review_evidence_refs=("terms:synthetic", "robots:synthetic", "privacy:synthetic"),
        ),
        html="""<html><body><article class='company'>
        <span class='name'>Test Solar Company</span>
        <a href='/members/testsolar'>Details</a></article></body></html>""",
        observed_at=NOW,
    )


def identity_review(**overrides):
    opts = dict(
        vertical="solar", target_kind="contractor", jurisdiction="GB-ENG",
        company_identity_ref="entity:synthetic-reviewed-sole-company",
        verified_first_party_website="https://solar-firm.example/",
        website_verification_ref="first_party_website:synthetic-verified",
    )
    opts.update(overrides)
    return EvidenceReview(**opts)


def test_scrapling_real_parser_extracts_bounded_static_contacts():
    pytest.importorskip("scrapling")
    result = SiteCrawler(
        offline_extractor=ScraplingBusinessContactExtractor()
    ).extract_offline_html(HTML, "https://solar-firm.example/contact")
    assert result.error == ""
    assert result.pages_crawled == 1
    assert result.has_contact
    emails = [c.email for c in result.contacts if c.email]
    assert "office@solar-firm.example" in emails
    assert "contact@solar-firm.example" in emails
    assert "secrets@should-not-extract.example" not in emails
    assert any(c.phone == "+442079460001" for c in result.contacts)
    assert all(c.source_url == "https://solar-firm.example/contact"
               for c in result.contacts)


def test_reviewed_existing_waterfall_can_use_scrapling_offline():
    pytest.importorskip("scrapling")
    flow, plan = build_reviewed_scrapling_waterfall(
        source_report=source_report(), review=identity_review(),
        html=HTML, website_page_url="https://solar-firm.example/contact",
        observed_at=NOW,
    )
    assert [p.name for p in flow.providers] == [
        "empire_hunter", "registry_scraper", "site_crawler_scrapling_offline"
    ]
    assert flow.gate.min_confidence == build_default_waterfall().gate.min_confidence
    assert flow.max_attempts == 3
    assert plan["state"] == "EVIDENCE_REVIEW_READY"
    provider = flow.providers[2]
    obs = provider.search({"company": "Test Solar Company"})
    assert obs.email == "office@solar-firm.example"
    assert obs.raw["bound_to_decision_maker"] is False
    assert flow.gate.validate(obs) is False
    assert provider.search({"company": "Wrong firm"}) is None


def test_bad_site_host_never_injected_into_waterfall():
    with pytest.raises(ValueError, match="verified owned"):
        build_reviewed_scrapling_waterfall(
            source_report=source_report(), review=identity_review(),
            html=HTML, website_page_url="https://evil.example/contact",
            observed_at=NOW,
        )


def test_unapproved_claimant_and_missing_identity_never_get_provider():
    p = identity_review(vertical="mass_torts", target_kind="claimant")
    with pytest.raises(ValueError, match="review held"):
        build_reviewed_scrapling_waterfall(
            source_report=source_report(), review=p,
            html=HTML, website_page_url="https://solar-firm.example/contact",
            observed_at=NOW,
        )


def test_no_scrapling_engine_configured_fails_closed():
    result = SiteCrawler().extract_offline_html(
        HTML, "https://solar-firm.example/contact",
    )
    assert result.error == "offline_extractor_not_configured"
    assert result.contacts == []
    assert result.pages_crawled == 0


@pytest.mark.parametrize("url", [
    "http://solar-firm.example/contact",
    "https://localhost/contact",
    "https://127.0.0.1/contact",
    "https://10.0.0.1/contact",
    "https://solar-firm.example:8443/contact",
    "https://solar-firm.internal/contact",
])
def test_scrapling_contact_parser_no_internal_or_insecure_origin(url):
    with pytest.raises(ScraplingExtractionHeld):
        ScraplingBusinessContactExtractor().extract_contacts(
            HTML, url=url, page_type="contact"
        )


def test_html_document_budget_bounded():
    with pytest.raises(ScraplingExtractionHeld, match="oversize"):
        ScraplingBusinessContactExtractor().extract_contacts(
            "x" * 513_000, url="https://solar-firm.example/contact",
            page_type="contact",
        )


def test_production_default_chain_unchanged_after_unification():
    default = build_default_waterfall()
    assert [p.name for p in default.providers] == [
        "registry_scraper", "site_crawler", "empire_hunter"
    ]


def test_gov_scrapling_provider_never_calls_network(monkeypatch):
    pytest.importorskip("scrapling")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("unexpected HTTP request")))
    flow, _ = build_reviewed_scrapling_waterfall(
        source_report=source_report(), review=identity_review(),
        html=HTML, website_page_url="https://solar-firm.example/contact",
        observed_at=NOW,
    )
    assert flow.providers[2].search({"company": "Test Solar Company"}).email
    observation = flow.observe_scrapling_only({"company": "Test Solar Company"})
    assert observation["observed"] is True
    assert observation["existing_gate_would_pass"] is False
    assert observation["outbound_authorized"] is False
    with pytest.raises(PermissionError, match="offline_source_review"):
        flow.enrich({"company": "Test Solar Company"})


def test_one_synthetic_firm_source_to_identity_to_owned_waterfall():
    """Combined path: source evidence -> no-write identity -> offline Waterfall."""
    pytest.importorskip("scrapling")
    from empire_os.scrapling_identity_review import (
        review_scrapling_canonical_identity,
    )
    source = source_report()
    reviewed = identity_review()
    identity = review_scrapling_canonical_identity(
        report=source,
        review=reviewed,
        canonical_rows=[{
            "id": "canonical-synthetic-001",
            "business_name": "Test Solar Company",
            "phone": "",
            "niche": "solar",
            "metro": "London",
        }],
        canonical_snapshot_complete=True,
        canonical_snapshot_ref="snapshot:synthetic-full-identity-001",
        now=NOW,
    )
    proposal = identity["observation_decisions"][0]
    assert proposal["state"] == "POTENTIAL_EXISTING_REVIEW"
    assert proposal["possible_canonical_ids"] == ["canonical-synthetic-001"]
    assert proposal["canonical_prospect_id_verified"] is None
    flow, plan = build_reviewed_scrapling_waterfall(
        source_report=source,
        review=reviewed,
        html=HTML,
        website_page_url="https://solar-firm.example/contact",
        observed_at=NOW,
    )
    observed = flow.observe_scrapling_only({"company": "Test Solar Company"})
    assert plan["state"] == "EVIDENCE_REVIEW_READY"
    assert observed["observed"] is True
    assert observed["existing_gate_would_pass"] is False
    assert observed["canonical_database_writes"] is False
    assert identity["unique_canonical_leads_verified_added"] == 0
    with pytest.raises(PermissionError):
        flow.enrich({"company": "Test Solar Company"})
