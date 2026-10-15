"""Existing SEO Director copy integrated without changing intake or buyer routes."""
from pathlib import Path
import hashlib
import subprocess

from bs4 import BeautifulSoup
import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "apps/empire-public-site"
ORIGINAL = Path("/var/tmp/empire_b2b_copy_component_handoff_20261014")
SOURCES = {
    "commercial": (
        "CommercialBuyerExplanation.tsx",
        "commercial.explanation.review.tsx",
        "efaa10def0238605a824dc31618accd8324424e96668ff5c9e56dc2a4bcea330",
        "Start with the business problem, not a product label",
    ),
    "predictive-revenue": (
        "PredictiveRevenueBuyerExplanation.tsx",
        "predictive-revenue.explanation.review.tsx",
        "30525e1d1181f76975c9abdcd642dc35583aa53089a2f58c9a9d88f4df590e0f",
        "What is predictive revenue intelligence?",
    ),
}


@pytest.mark.parametrize("page", SOURCES)
def test_original_seo_director_source_hash_and_no_new_tracking(page):
    component, handoff, digest, heading = SOURCES[page]
    source = (SITE / "src/components" / component).read_bytes()
    assert hashlib.sha256(source).hexdigest() == digest
    assert source == (ORIGINAL / handoff).read_bytes()
    text = source.decode()
    assert heading in text
    assert text.count("<article") == 5
    assert "<form" not in text
    assert "<script" not in text
    assert "<iframe" not in text
    assert "tel:" not in text
    assert "/r/" not in text
    assert "realised revenue" in text.lower() or "delivery capacity" in text.lower()


@pytest.mark.parametrize("page", SOURCES)
def test_existing_consent_and_endpoints_untouched_by_editorial(page):
    component = SOURCES[page][0].removesuffix(".tsx")
    relative = "apps/empire-public-site/src/app/" + page + "/page.tsx"
    current = (ROOT / relative).read_text()
    prior = subprocess.check_output(["git", "-C", str(ROOT), "show", "HEAD:" + relative], text=True)
    assert current.count('import ' + component) == 1
    assert current.count('<' + component + ' />') == 1
    changed_only = current.replace(
        'import ' + component + ' from "@/components/' + component + '";\n', ''
    ).replace('<' + component + ' />', '').replace("\n        \n", "\n")
    # Checkout POST, agreed contact scope, required form, and privacy text are
    # independently checked without depending on whitespace replacement.
    for required in (
        'contact_consent:',
        'I am not signing up for unrelated marketing.',
        'href="/privacy"',
        '/v1/checkout/',
        'type="checkbox"',
    ):
        assert current.count(required) == prior.count(required)
    assert current.count('method: "POST"') == prior.count('method: "POST"')
    assert current.count('idempotency_key:') == prior.count('idempotency_key:')
    assert '<form' not in (SITE / 'src/components' / (component + '.tsx')).read_text()


def test_static_site_contains_both_editorials_and_keeps_buyer_noindex():
    out = SITE / 'out'
    for slug, (_, _, _, heading) in SOURCES.items():
        doc = BeautifulSoup((out / (slug + '.html')).read_text(), 'html.parser')
        assert len(doc.select('main')) == 1
        assert len(doc.select('h1')) == 1
        assert heading in doc.get_text(' ', strip=True)
        assert heading in [h.get_text(' ', strip=True) for h in doc.select('h2')]
        assert len(doc.select('main article[id]')) >= 5
        assert len(doc.select('form')) == 1
        assert len(doc.select('form input[type="checkbox"][required]')) == 1
        assert len(doc.select('form a[href="/privacy"]')) == 1
        assert len(doc.select('link[rel="canonical"]')) == 1
        assert not doc.select('a[href^="/r/"],a[href^="tel:"],form a[href^="http:"]')
    roofing = BeautifulSoup((out / 'roofing.html').read_text(), 'html.parser')
    assert any('noindex' in str(x.get('content','')).lower() for x in roofing.select('meta[name="robots"]'))
    for slug in ('roofing','solar'):
        industry = BeautifulSoup((out/'industries'/f'{slug}.html').read_text(),'html.parser')
        assert len(industry.select('h1')) == 1
        assert industry.select_one('a[href="/commercial"]') is not None
