"""Commercial TAM buying-intent content must stay original, accurate and safe."""
from pathlib import Path
import hashlib
import json
from bs4 import BeautifulSoup
import pytest

from empire_os.search_intelligence.seo_publication_impact_review import review_publication_impact
from tests.search_intelligence.test_seo_publication_impact_review_20261015 import inputs

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'apps/empire-public-site'
BUILT=SITE/'out'


def guide():
    path=BUILT/'commercial.html'
    return BeautifulSoup(path.read_text('utf-8'),'html.parser')


def test_original_tam_answer_crawlable_with_four_evidence_steps_three_faq():
    doc=guide()
    section=doc.select_one('section#tam-buying-intent')
    assert section is not None
    title=section.select_one('h2#tam-buyer-intent-heading')
    assert title.get_text(' ',strip=True)==('Which companies in your total addressable market '
                                             'are actually ready to buy?')
    assert len(section.select('ol li'))==4
    assert len(section.select('article'))==3
    plain=section.get_text(' ',strip=True)
    for word in ('total addressable market', 'actual decision', 'consent',
                 'buying intent', 'realised revenue', 'source', 'accepting downstream buyer'):
        assert word in plain.lower()
    assert not any(x in plain.lower() for x in ('guaranteed conversion', 'already paying', '100% accuracy'))
    assert len(doc.select('main'))==1
    assert len(doc.select('h1'))==1
    assert len(doc.select('form'))==1
    assert len(doc.select('form input[type=checkbox][required]'))==1
    assert len(doc.select('form a[href="/privacy"]'))==1
    assert len(doc.select('#commercial-enquiry'))==1
    assert section.select_one('a[href="#commercial-enquiry"]') is not None
    assert len(doc.select('main article[id]'))>=5
    assert not doc.select('section#tam-buying-intent form,section#tam-buying-intent script')
    assert not doc.select('section#tam-buying-intent a[href^="/r/"],section#tam-buying-intent a[href^="tel:"]')
    assert doc.select_one('link[rel="canonical"]').get('href')=='https://empire-ai.co.uk/commercial'


def test_legacy_buyer_intent_404_not_activated_as_redirect_or_created_route():
    assert not (SITE/'src/app/aeo/accounting/TAM').exists()
    assert not (BUILT/'aeo/accounting/TAM.html').exists()
    assert 'data:' not in (SITE/'src/components/TamBuyingIntentEvidenceGuide.tsx').read_text()
    assert 'onClick=' not in (SITE/'src/components/TamBuyingIntentEvidenceGuide.tsx').read_text()


def test_component_does_not_change_original_astra_buyer_explanations():
    p=SITE/'src/components/CommercialBuyerExplanation.tsx'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='efaa10def0238605a824dc31618accd8324424e96668ff5c9e56dc2a4bcea330'
    p=SITE/'src/components/PredictiveRevenueBuyerExplanation.tsx'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='30525e1d1181f76975c9abdcd642dc35583aa53089a2f58c9a9d88f4df590e0f'


def test_actual_site_build_protects_every_other_page_from_editorial():
    for slug in ('roofing','solar','hvac','property','legal-mass-tort'):
        doc=BeautifulSoup((BUILT/'industries'/f'{slug}.html').read_text('utf-8'),'html.parser')
        assert doc.select_one('#tam-buying-intent') is None
    for rel in ('predictive-revenue.html','buy.html','roofing.html','index.html'):
        doc=BeautifulSoup((BUILT/rel).read_text('utf-8'),'html.parser')
        assert doc.select_one('#tam-buying-intent') is None
    consumer=BeautifulSoup((BUILT/'roofing.html').read_text('utf-8'),'html.parser')
    assert any('noindex' in str(x.get('content','')).lower() for x in consumer.select('meta[name=robots]'))


def test_fourth_receipt_requires_exact_commercial_page_scope_and_hash():
    input_=inputs()
    fourth={**input_['latest_release'],'pages':{'commercial.html':{'after_sha256':'d'*64}}}
    input_['tam_answer_release']=fourth
    input_['live_pages']['/commercial']['sha256']='d'*64
    result=review_publication_impact(**input_)
    assert result['original_tam_buyer_explainer_release_verified'] is True
    assert result['seo_pages_verified_public']==4
    assert result['accepted_click_count'] is None
    assert result['paid_cpc_revenue'] is None
    assert result['production_site_modified'] is False
    assert result['publisher_pay_per_click_live'] is False
    assert result['buyer_outbound_authorized'] is False
    assert 'TAM/' not in json.dumps(result)


def test_fourth_receipt_rejects_extra_or_missing_pages():
    input_=inputs()
    fourth={**input_['latest_release'],'pages':{'commercial.html':{'after_sha256':'d'*64},'buy.html':{'after_sha256':'d'*64}}}
    input_['tam_answer_release']=fourth
    with pytest.raises(ValueError,match='incorrect_reviewed_release_page_scope'):
        review_publication_impact(**input_)
    fourth['pages']={'buy.html':{'after_sha256':'d'*64}}
    with pytest.raises(ValueError,match='incorrect_reviewed_release_page_scope'):
        review_publication_impact(**input_)


def test_missing_fourth_receipt_rejects_unreviewed_live_commercial_change():
    input_=inputs()
    input_['live_pages']['/commercial']['sha256']='d'*64
    with pytest.raises(ValueError,match='published_page_not_current_verified_release'):
        review_publication_impact(**input_)
