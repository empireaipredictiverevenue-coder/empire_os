"""Google-facing metadata must accurately describe two published B2B pages."""
from pathlib import Path
from bs4 import BeautifulSoup
import pytest

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'apps/empire-public-site'
ROUTE=SITE/'src/app/industries/[slug]/page.tsx'

EXPECTED={
    'roofing':{
        'title':'Roofing Demand & Call Qualification | Empire AI',
        'description':'Explore roofing demand, eligible service areas, first-party enquiry quality and how buyers define payable calls. Evidence-first commercial intelligence.',
        'evidence':'From a roofing search to a qualified commercial opportunity.',
    },
    'solar':{
        'title':'Solar Demand & Referral Qualification | Empire AI',
        'description':'Understand solar demand, installer coverage, qualified enquiries and the difference between organic clicks, accepted leads and paid referrals.',
        'evidence':'Solar referrals only become revenue when the buyer accepts the outcome.',
    },
}


def check_export(root:Path)->dict:
    result={}
    for slug,expected in EXPECTED.items():
        doc=BeautifulSoup((root/'industries'/f'{slug}.html').read_text(encoding='utf-8'),'html.parser')
        title=doc.title.get_text(' ',strip=True)
        meta=doc.select('meta[name="description"]')
        og_title=doc.select('meta[property="og:title"]')
        og_desc=doc.select('meta[property="og:description"]')
        canonical=doc.select('link[rel="canonical"]')
        if title!=expected['title'] or len(meta)!=1 or meta[0].get('content')!=expected['description']:
            raise ValueError('search_title_or_description_not_matching_original_buyer_copy')
        if len(og_title)!=1 or og_title[0].get('content')!=title:
            raise ValueError('open_graph_title_not_matching_search_title')
        if len(og_desc)!=1 or og_desc[0].get('content')!=meta[0].get('content'):
            raise ValueError('open_graph_description_not_matching_page')
        if len(canonical)!=1 or canonical[0].get('href')!=f'https://empire-ai.co.uk/industries/{slug}':
            raise ValueError('canonical_page_regressed')
        if len(doc.select('main'))!=1 or len(doc.select('h1'))!=1 or expected['evidence'] not in doc.get_text(' ',strip=True):
            raise ValueError('original_buyer_content_missing')
        if not doc.select('main a[href="/commercial"]'):
            raise ValueError('existing_first_party_business_enquiry_missing')
        if doc.select('a[href^="/r/"],a[href^="tel:"],form'):
            raise ValueError('payable_referral_or_unapproved_consumer_form_detected')
        result[slug]={'metadata_matches_visible_copy':True,'self_canonical':True,
                      'site_live':False,'buyer_contract_verified':False}
    return result


def test_original_buying_metadata_static_export_build():
    result=check_export(SITE/'out')
    assert set(result)=={'roofing','solar'}
    assert all(x['metadata_matches_visible_copy'] and x['buyer_contract_verified'] is False for x in result.values())


def test_both_exact_b2b_slug_metadata_without_affecting_other_industries():
    code=ROUTE.read_text(encoding='utf-8')
    for slug,entry in EXPECTED.items():
        assert f'{slug}: {{' in code
        assert entry['title'] in code
        assert entry['description'] in code
    assert 'const seoTitle = searchCopy?.title ??' in code
    assert 'const seoDescription = searchCopy?.description ?? page.subtitle;' in code
    assert 'title: searchCopy?.title ?? page.title,' in code
    assert 'description: searchCopy?.description ?? page.subtitle,' in code
    assert 'canonical: `/industries/${page.slug}`' in code
    assert 'noindex' not in code
    assert 'leadsmart' not in code.lower()


@pytest.mark.parametrize('slug', ['roofing','solar'])
def test_title_concise_distinct_and_no_unsigned_revenue_promises(slug):
    title=EXPECTED[slug]['title']
    meta=EXPECTED[slug]['description']
    assert len(title)<=65 and len(meta)<=165
    assert title.endswith(' | Empire AI')
    assert len({x['title'] for x in EXPECTED.values()})==2
    assert not any(word in (title+' '+meta).lower()
                   for word in ('guaranteed', 'we pay', '$', '£', 'live calls today', 'nationwide approval'))
    assert 'payable' not in meta.lower() or 'how buyers define payable calls' in meta.lower()


def test_consumer_roofing_noindex_remains_in_export():
    doc=BeautifulSoup((SITE/'out/roofing.html').read_text('utf-8'),'html.parser')
    assert any('noindex' in str(x.get('content','')).lower() for x in doc.select('meta[name="robots"]'))
