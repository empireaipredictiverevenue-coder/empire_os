"""SEO visits cannot become fake payable clicks, leads or buyer contracts."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from empire_os.search_intelligence.organic_ppc_commercial_review import (
    PAGE_PATHS, RESEARCH_LANES, review_owned_organic_ppc,
)
from scripts import inspect_owned_organic_ppc_readiness as operator


BASE_DATE = date(2026, 10, 15)


def baseline():
    return {
        "schema_version": "empire.search.owned_gsc_organic_review.v1",
        "tenant_id": "empire-ai", "site_id": "empire-ai.co.uk",
        "gsc_property": "sc-domain:empire-ai.co.uk",
        "mode": "OBSERVE",
        "window": {"start":"2026-09-15","end":"2026-10-13"},
        "measurement_status": "GSC_DAILY_SITEWIDE_PLUS_QUERY_PAGE",
        "sitewide_current":{"impressions":83,"clicks":1,"commercial_source_attribution_verified":False},
        "sitewide_previous":{"impressions":168,"clicks":3,"commercial_source_attribution_verified":False},
        "production_mutation":False,"direct_publishing_allowed":False,
        "outbound_allowed":False,
    }


def pages():
    rows=[]
    for path in PAGE_PATHS:
        rows.append({"path":path,"http":200,"title_present":True,
                     "h1_count":1,"canonical":"https://empire-ai.co.uk"+path,
                     "robots":"noindex, nofollow" if path=="/roofing" else "",
                     "description_present":True})
    for row in rows:
        if row["path"] in ("/privacy", "/terms"):
            row["canonical"]=None
    return rows


def report(**kw):
    return review_owned_organic_ppc(baseline(),pages=pages(),
        www_home_http=kw.get('www_home_http',200),
        www_home_redirect_location=kw.get('location'))


def test_real_production_shaped_baseline_yields_honest_tasks_not_click_revenue():
    r=report()
    assert r['schema_version']=='empire.search.owned_organic_ppc_commercial_review.v1'
    assert r['observed_gsc_sitewide']=={
        'impressions':83,'clicks':1,'comparison_impressions':168,
        'comparison_clicks':3,
    }
    assert r['search_clicks_are_payable_advertiser_clicks'] is False
    assert r['gsc_query_page_data_is_sitewide_complete'] is False
    assert r['buyer_roofing_page_held_noindex'] is True
    assert r['www_host_redirect_to_canonical_verified'] is False
    assert r['technical_indexability_signal_count']==5
    assert r['monetization_models']['PUBLISHER_PPC']['status']=='NO_VERIFIED_PAYABLE_CPC_BUYER'
    assert r['monetization_models']['PAY_PER_CALL']['phone_route_enabled'] is False
    assert r['monetization_models']['PAID_SEARCH_ADS']['daily_budget_authorized'] is False
    assert r['paid_media_spend_authorized'] is False
    assert r['live_referral_redirects_enabled'] is False
    assert r['revenue_recognition_authorized'] is False
    assert r['confirmed_payable_click_count'] is None
    assert r['buyer_paid_click_revenue_verified'] is False
    assert r['execution_authority']=='none'
    actions=[x['action'] for x in r['next_actions']]
    assert 'REVIEW_ORGANIC_DEMAND_DECLINE' in actions
    assert 'REVIEW_WWW_CANONICAL_REDIRECT_PARITY' in actions
    assert 'OBTAIN_SIGNED_PAYABLE_OUTBOUND_CPC_BUYER_TERMS' in actions
    assert 'CREATE_ONE_ORIGINAL_HIGH_INTENT_PILLAR_CONTENT_REVIEW' in actions
    assert sum(x=='REVIEW_PUBLISHED_LEGAL_PAGE_CANONICAL' for x in actions)==2
    assert all('approved' not in k.lower() for k in r if k.startswith('buyer_'))
    assert all(x['accepted_click_payout_terms_verified'] is False for x in r['research_programmes'])
    assert {x['market'] for x in r['research_programmes']} == {'USA','UK','AU','CA','MULTIMARKET'}
    assert len(RESEARCH_LANES)==6


def test_even_high_search_traffic_does_not_prove_payable_cpc():
    x=baseline()
    x['sitewide_current']['impressions']=100000
    x['sitewide_current']['clicks']=10000
    r=review_owned_organic_ppc(x,pages=pages(),www_home_http=301,
        www_home_redirect_location='https://empire-ai.co.uk/')
    assert r['observed_gsc_sitewide']['clicks']==10000
    assert r['buyer_paid_click_revenue_verified'] is False
    assert r['monetization_models']['PUBLISHER_PPC']['accepted_outbound_clicks'] is None
    assert r['live_click_attribution_enabled'] is False
    assert r['production_publish_authorized'] is False
    assert r['www_host_redirect_to_canonical_verified'] is True


def test_buyer_roofing_landing_noindex_is_not_automatically_removed():
    p=pages()
    next(x for x in p if x['path']=='/roofing')['robots']='index, follow'
    r=review_owned_organic_ppc(baseline(),pages=p,www_home_http=200,
        www_home_redirect_location=None)
    assert r['buyer_roofing_page_held_noindex'] is False
    issue=next(x for x in r['next_actions'] if x['action']=='RESTORE_BUYER_ROOFING_NOINDEX_HOLD')
    assert issue['production_traffic_authorized'] is False
    assert r['live_buyers_authorized'] is False


@pytest.mark.parametrize(('key','value'),[
    ('tenant_id','other'),('site_id','someone-else.com'),
    ('gsc_property','sc-domain:other.com'),('mode','EXECUTE'),
    ('measurement_status','QUERY_PAGE_ONLY_SITEWIDE_UNKNOWN'),
    ('production_mutation',True),('direct_publishing_allowed',True),
    ('outbound_allowed',True),
])
def test_no_cross_tenant_or_claimed_execution_evidence(key,value):
    x=baseline();x[key]=value
    with pytest.raises(ValueError):
        review_owned_organic_ppc(x,pages=pages(),www_home_http=200,
                                 www_home_redirect_location=None)


@pytest.mark.parametrize(('key','value'),[
    ('impressions',True),('impressions',-1),('clicks',5.0),('clicks',1000),
    ('commercial_source_attribution_verified',True),
])
def test_no_forged_google_click_counts_or_commercial_source(key,value):
    x=baseline();x['sitewide_current'][key]=value
    with pytest.raises(ValueError):
        review_owned_organic_ppc(x,pages=pages(),www_home_http=200,
                                 www_home_redirect_location=None)


def test_scope_rejects_duplicate_missing_or_cross_domain_canonical():
    p=pages()
    with pytest.raises(ValueError):
        review_owned_organic_ppc(baseline(),pages=p[:-1],www_home_http=200,
                                 www_home_redirect_location=None)
    p[0]['path']='/roofing'
    with pytest.raises(ValueError):
        review_owned_organic_ppc(baseline(),pages=p,www_home_http=200,
                                 www_home_redirect_location=None)
    p=pages();p[0]['canonical']='https://advertiser.example/secret'
    with pytest.raises(ValueError):
        review_owned_organic_ppc(baseline(),pages=p,www_home_http=200,
                                 www_home_redirect_location=None)


def test_www_unapproved_redirect_host_is_rejected():
    with pytest.raises(ValueError):
        review_owned_organic_ppc(baseline(),pages=pages(),www_home_http=301,
            www_home_redirect_location='https://evil.example/phish')


def _fake_get_factory(urls):
    seen=[]
    def fake_get(url, **kw):
        seen.append((url,kw))
        assert kw['allow_redirects'] is False
        assert kw['timeout'] == 7
        assert kw['headers']['User-Agent'].startswith('EmpireOS-Owned-')
        return urls[url]
    return fake_get,seen


def _response(body,*,status=200,headers=None):
    return SimpleNamespace(status_code=status,content=body.encode(),text=body,
                           headers=headers or {})


def test_one_shot_probe_fetches_only_fixed_first_party_urls_and_no_redirects(tmp_path,monkeypatch):
    def html(path):
        return ('<html><head><title>Empire Source</title>'
                '<meta name="description" content="Original research">'
                '<link rel="canonical" href="https://empire-ai.co.uk'+path+'">'
                + ('<meta name="robots" content="noindex,nofollow">' if path=='/roofing' else '')
                + '</head><body><h1>Original source</h1></body></html>')
    urls={operator.ORIGIN+path:_response(html(path)) for path in PAGE_PATHS}
    urls[operator.WWW]=_response(html('/'))
    get,seen=_fake_get_factory(urls)
    results,www_status,location=operator.probe_owned_pages(getter=get)
    assert len(seen)==len(PAGE_PATHS)+1
    assert len(results)==len(PAGE_PATHS)
    assert www_status==200 and location is None
    assert next(p for p in results if p['path']=='/roofing')['robots']=='noindex,nofollow'
    output=review_owned_organic_ppc(baseline(),pages=results,
        www_home_http=www_status,www_home_redirect_location=location)
    assert output['paid_media_spend_authorized'] is False
    assert all('body' not in r and 'html' not in r for r in output['owned_pages'])


def test_probe_rejects_external_www_location_without_forwarding_or_echoing():
    urls={operator.ORIGIN+path:_response('<html></html>',status=404) for path in PAGE_PATHS}
    urls[operator.WWW]=_response('',status=301,headers={'Location':'https://evil.example/private'})
    get,seen=_fake_get_factory(urls)
    _,www_code,location=operator.probe_owned_pages(getter=get)
    assert www_code==301 and location is None
    assert all(u.startswith(('https://empire-ai.co.uk/','https://www.empire-ai.co.uk/')) for u,_ in seen)


def test_operator_uses_existing_gsc_evidence_without_sending_or_production_writes(tmp_path,monkeypatch):
    local=tmp_path/'observed_gsc.json';local.write_text(json.dumps(baseline()))
    monkeypatch.setattr(operator,'BASELINE_ROOT',tmp_path)
    monkeypatch.setattr(operator,'probe_owned_pages',lambda getter: (pages(),200,None))
    output=operator.run(baseline_path=local,getter=lambda *a,**k:None,today=BASE_DATE)
    assert output['observed_gsc_sitewide']['impressions']==83
    assert output['execution_authority']=='none'
    assert output['outbound_authorized'] is False
    assert output['live_click_attribution_enabled'] is False
    assert output['revenue_recognition_authorized'] is False
    stale=baseline();stale['window']['end']='2026-09-15'
    local.write_text(json.dumps(stale))
    with pytest.raises(ValueError,match='stale'):
        operator.run(baseline_path=local,getter=lambda *a,**k:None,today=BASE_DATE)
    local.unlink()
    local.symlink_to(tmp_path/'other')
    with pytest.raises(ValueError,match='symlink'):
        operator.run(baseline_path=local,getter=lambda *a,**k:None,today=BASE_DATE)
