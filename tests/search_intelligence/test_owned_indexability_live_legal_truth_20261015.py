"""Live legal routes must not break SEO truth or activate the buyer funnel."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import pytest

from empire_os.search_intelligence.owned_indexability_review import analyse_owned_indexability

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/probe_owned_seo_indexability.py'
ORIGIN='https://empire-ai.co.uk'
GATED=(
    '/roofing','/roofing/replacement-vs-repair','/roofing/installation-checklist',
    '/research/agent-governance','/privacy','/terms',
)


def input_data():
    sitemap=b'''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://empire-ai.co.uk/</loc></url><url><loc>https://empire-ai.co.uk/industries/roofing</loc></url></urlset>'''
    pages=[{'url':ORIGIN+path,'http':200,'html_robots':[], 'xrobots':[],
            'canonical':[ORIGIN+path if path!='/' else ORIGIN],
            'h1_count':1,'title':'Original evidence-based company page'}
           for path in ('/','/industries/roofing')]
    gates=[]
    for path in GATED:
        public=path in ('/roofing','/privacy','/terms')
        gates.append({
            'path':path,'http':200 if public else 404,
            'html_robots':['noindex,nofollow'] if path=='/roofing' else [],
            'xrobots':[],
            'canonical':[] if path in ('/privacy','/terms') else [],
            'title':'Empire AI policy' if path in ('/privacy','/terms') else '',
            'h1_count':1 if path in ('/privacy','/terms') else 0,
        })
    return {'sitemap':sitemap,
            'robots':b'User-agent: *\nAllow: /\nSitemap: https://empire-ai.co.uk/sitemap.xml\n',
            'pages':pages,'gated_pages':gates,
            'observed_at':'2026-10-15T18:00:00+00:00'}


def run(data=None):
    return analyse_owned_indexability(**(data or input_data()))


def test_live_legal_pages_200_recorded_without_owner_signoff():
    result=run()
    assert result['sitemap_url_count']==2
    assert result['needs_technical_review_count']==0
    assert result['sitemap_indexability_signal_count']==2
    for item in result['published_legal_pages_review']:
        assert item['observed_http']==200
        assert item['status']=='PUBLIC_TECHNICAL_METADATA_INCOMPLETE'
        assert item['legal_owner_release_verified'] is False
        assert item['page_publication_mutation_allowed'] is False
        assert item['canonical_present'] is False
        assert item['title_and_h1_present'] is True
    assert result['legal_publication_approval_inferred'] is False
    assert result['existing_approved_roofing_page_is_intentionally_noindex'] is True
    assert result['remove_buyer_noindex_allowed'] is False
    assert result['publication_authorized'] is False
    assert result['outbound_authorized'] is False
    assert result['revenue_verified'] is False
    assert result['production_write'] is False
    assert result['google_indexation_verified'] is False


def test_legal_self_canonical_does_not_infer_approval():
    packet=input_data()
    for row in packet['gated_pages']:
        if row['path'] in ('/privacy','/terms'):
            row['canonical']=[ORIGIN+row['path']]
    result=run(packet)
    assert all(x['status']=='PUBLIC_TECHNICAL_SIGNALS_PRESENT_REVIEW_ONLY'
               for x in result['published_legal_pages_review'])
    assert result['legal_publication_approval_inferred'] is False
    assert result['publication_authorized'] is False


def test_published_legal_missing_title_remains_review_issue():
    packet=input_data()
    next(x for x in packet['gated_pages'] if x['path']=='/privacy')['title']=''
    row=next(x for x in run(packet)['published_legal_pages_review']
             if x['path']=='/privacy')
    assert row['title_and_h1_present'] is False
    assert row['status']=='PUBLIC_TECHNICAL_METADATA_INCOMPLETE'


def test_live_legal_unknown_http_fails_closed():
    packet=input_data()
    next(x for x in packet['gated_pages'] if x['path']=='/terms')['http']=302
    with pytest.raises(ValueError,match='legal_page_unexpected_http_status'):
        run(packet)


def test_only_unreleased_guide_remains_hard_publication_hold():
    packet=input_data()
    next(x for x in packet['gated_pages']
         if x['path']=='/roofing/installation-checklist')['http']=200
    with pytest.raises(ValueError,match='unreleased_or_legal_route_in_public_view'):
        run(packet)


def test_buyer_roofing_noindex_must_not_be_lifted():
    packet=input_data()
    next(x for x in packet['gated_pages'] if x['path']=='/roofing')['html_robots']=[]
    with pytest.raises(ValueError,match='leadsmart_buyer_landing_accidentally_indexable'):
        run(packet)


def test_200_legal_pages_not_automatically_put_in_sitemap():
    result=run()
    assert result['expected_gated']['/privacy']['publication_allowed'] is False
    assert result['expected_gated']['/terms']['publication_allowed'] is False
    assert result['sitemap_url_count']==2


def test_one_shot_operator_with_public_legal_pages(tmp_path):
    spec=importlib.util.spec_from_file_location('seo_review_1510',SCRIPT)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    packet=input_data()
    requested=[]
    def fake_fetch(url):
        requested.append(url)
        if url==ORIGIN+'/robots.txt':
            return {'url':url,'http':200,'body':packet['robots']}
        if url==ORIGIN+'/sitemap.xml':
            return {'url':url,'http':200,'body':packet['sitemap']}
        if any(p['url']==url for p in packet['pages']):
            data=next(p for p in packet['pages'] if p['url']==url)
            return {**data,'body':b'No public HTML retained'}
        if url==ORIGIN+'/roofing':
            return {'url':url,'http':200,'html_robots':['noindex,nofollow'],
                    'xrobots':[],'canonical':[],'h1_count':1,'title':'Buyer gated'}
        data=next((p for p in packet['gated_pages'] if ORIGIN+p['path']==url),None)
        assert data is not None
        return {'url':url,**data}
    dest=tmp_path/'truth.json'
    outcome=mod.run(output=dest,get=fake_fetch,allowed_root=tmp_path)
    assert outcome['status']=='OWNED_INDEXABILITY_AUDIT_RECORDED'
    assert outcome['gated_pages_verified']==6
    assert outcome['google_indexed_pages_verified'] is False
    recorded=json.loads(dest.read_text())
    assert len(requested)==10
    assert recorded['production_db_changed'] is False
    assert recorded['website_changed'] is False
    assert recorded['review']['published_legal_pages_review'][0]['observed_http']==200
    assert 'No public HTML retained' not in dest.read_text()
    assert dest.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError,match='new_private_review_receipt_required'):
        mod.run(output=dest,get=fake_fetch,allowed_root=tmp_path)
