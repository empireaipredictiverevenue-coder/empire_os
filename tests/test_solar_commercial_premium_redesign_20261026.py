"""Candidate-only source and generated page checks. Never submits a real enquiry."""
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"apps/empire-public-site"
PROD=Path("/srv/empire_os/apps/empire-public-site")
SOLAR=APP/"src/components/SolarIntelligenceExperience.tsx"
COMM=APP/"src/app/commercial/page.tsx"
ROUTE=APP/"src/app/industries/[slug]/page.tsx"

def file(path):return path.read_text()

def test_only_solar_uses_premium_component_not_other_industries():
    content=file(ROUTE)
    old=file(PROD/"src/app/industries/[slug]/page.tsx")
    assert 'if (page.slug === "solar") return <SolarIntelligenceExperience page={page} />;' in content
    assert "return <IndustryIntelligencePage page={page} />;" in content
    assert "if (!page) notFound();" in content
    assert content.count("generateStaticParams()")==1
    assert 'title: "Solar Market Intelligence & Installer Demand | Empire AI"' in content
    assert old.count("return <IndustryIntelligencePage page={page} />;")==1

def test_solar_only_existing_image_brand_consent_bounded_proposal():
    content=file(SOLAR)
    assert "solar-sunset-original.jpg" in content
    assert "bg-[#030916]" in content and "text-[#f1ca83]" in content
    assert 'industryCommercialProposalHref("solar")' in content
    assert "getBuyerEditorial(\"solar\")" in content
    assert "/industries/hvac" in content
    assert "No claim of ready-to-buy homeowners" in content
    assert "<form" not in content
    assert '<nav aria-label="Solar intelligence navigation"' not in content
    assert "Solar markets change." in content
    assert "fetch(" not in content
    assert "Math.random" not in content
    assert "guaranteed" not in re.sub(r"No claim of ready-to-buy homeowners, guaranteed installations", "", content)

def test_commercial_offer_and_form_behavior_unchanged():
    content=file(COMM)
    original=file(PROD/"src/app/commercial/page.tsx")
    # No changes to the existing canonical request attempt, product
    # allowlist or POST idempotency logic.
    start="  const [offers, setOffers]"
    stop="  return <main"
    assert content[content.index(start):content.index(stop)] == original[original.index(start):original.index(stop)]
    for marker in [
        "selectApprovedProposalOffer(requested, data.offers)",
        "claimed_entry_page: claimedEntryForReview(window.location.search)",
        "reuseCommercialInterestAttempt(",
        'fetch("/v1/checkout/commercial/interests", {',
        "idempotency_key: attempt.idempotencyKey",
        'contact_consent: consent',
        "I consent to Empire AI emailing me about this specific enquiry.",
        "Read the Empire AI privacy notice",
        "result?.decision === \"commercial_enquiry_recorded\"",
        "<BrokeragePremiumDiscovery />",
        "<CommercialBuyerExplanation />",
        "<TamBuyingIntentEvidenceGuide />",
    ]: assert marker in content
    assert content.count("<form onSubmit={submit}")==1
    assert '<nav aria-label="Commercial navigation"' not in content
    assert content.count('id="commercial-enquiry"')==1
    assert "No automatic order, payment" in content

def test_proposal_form_is_not_replaced_by_marketing_lead_form():
    content=file(COMM)
    for name in ("business","email","domain","industry","region","outcome","consent"):
        assert name in content
    assert "result?.decision === \"commercial_enquiry_recorded\"" in content
    assert "This page cannot place an order or accept payment." in content

def test_build_generated_pages_have_real_headings_and_anchor():
    out=APP/"out"
    if not (out/"commercial.html").is_file():
        raise AssertionError("reviewed Next static build required before acceptance")
    c=BeautifulSoup((out/"commercial.html").read_bytes(),"html.parser")
    s=BeautifulSoup((out/"industries/solar.html").read_bytes(),"html.parser")
    for soup in (c,s):
        assert len(soup.select("h1"))==1
        assert not soup.select('meta[name=robots][content*=noindex]')
        assert len(soup.select('link[rel=canonical]'))==1
    assert len(c.select("form"))==1
    assert len(c.select("section#commercial-enquiry"))==1
    assert len(c.select("section#premium-brokerage"))==1
    assert len(c.select("section#tam-buying-intent"))==1
    assert len(s.select("form"))==0
    assert len(s.select('a[href*="/commercial?entry="]'))>=2
    assert "Solar markets change." in s.get_text(" ",strip=True)
    assert "Turn intelligence into" in c.get_text(" ",strip=True)
    for p in [
       "src/components/SolarIntelligenceExperience.tsx",
       "src/app/commercial/page.tsx",
    ]: assert (APP/p).is_file()

def test_other_industry_source_untouched():
    for rel in (
        "src/components/IndustryIntelligencePage.tsx",
        "src/lib/industry-pages.ts",
        "src/lib/industry-buying-editorial.ts",
        "src/components/IndustryBuyerEditorialSection.tsx",
        "src/components/CommercialBuyerExplanation.tsx",
        "src/components/TamBuyingIntentEvidenceGuide.tsx",
        "src/components/BrokeragePremiumDiscovery.tsx",
        "src/lib/commercial-entry-review.ts",
        "src/lib/buyer-proposal-handoff.ts",
        "src/lib/commercial-interest-attempt.ts",
    ):
        assert (APP/rel).read_bytes()==(PROD/rel).read_bytes(),rel
