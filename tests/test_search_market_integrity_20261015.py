"""Cross-country search locales and NYC permit-corridor evidence must fail closed."""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from empire_os.buyer_acquisition_scout import _nyc_territory_evidence

search = importlib.import_module('empire_os.search_fabric.search')


@pytest.mark.parametrize(('query','expected'), [
    ('solar affiliate program Australia', ('AU', 'en-AU')),
    ('solar publisher UK', ('GB', 'en-GB')),
    ('solar publisher United Kingdom', ('GB', 'en-GB')),
    ('roofing publisher Great Britain', ('GB', 'en-GB')),
    ('roofing publisher USA', ('US', 'en-US')),
    ('roofing publisher United States', ('US', 'en-US')),
    ('Canadian solar buyer Canada', ('CA', None)),
    ('Canadian solar buyer Toronto Canada', ('CA', 'en-CA')),
    ('solar contractor Montreal Canada', ('CA', 'fr-CA')),
    ('roofing contractor Austin TX', ('US', 'en-US')),
    ('solar publisher Australia and Canada', (None,None)),
    ('solar publisher Sydney Australia UK', (None,None)),
    ('solar contractor London Australia', (None,None)),
    ('solar leads to help us', (None,None)),
    ('solar affiliate program', (None,None)),
])
def test_registry_grounded_country_routing_without_server_geo_guessing(query,expected):
    assert search._search_market_locale(query) == expected


@pytest.mark.parametrize(('query','expected_params'), [
    ('solar affiliate program Australia', {'cc':'AU','setlang':'en-AU','mkt':'en-AU'}),
    ('publisher leads Canada', {'cc':'CA'}),
    ('solar affiliate program Canada United Kingdom', {}),
])
def test_bing_uses_explicit_country_and_only_grounded_market_language(
    query, expected_params, monkeypatch,
):
    captured=[]
    monkeypatch.setattr(search, '_polite',lambda engine:None)
    monkeypatch.setattr(search, '_next_proxy',lambda:None)
    monkeypatch.setattr(search, '_engine_available',lambda name:True)
    monkeypatch.setattr(search, '_record_engine_success',lambda name:None)
    monkeypatch.setattr(search, '_decode_http_response',lambda response:'safe-serp-body')
    def fake_get(url, **kwargs):
        assert 'bing.com' in url
        captured.append(kwargs['params'])
        return SimpleNamespace(status_code=200)
    monkeypatch.setattr(search.requests, 'get',fake_get)
    engine=next(e for e in search.ENGINES if e['name']=='bing_html')
    assert search._fetch_locked(engine,query,5)=='safe-serp-body'
    assert len(captured)==1
    params=captured[0]
    assert params['q']==query
    for key in ('cc','setlang','mkt'):
        assert params.get(key)==expected_params.get(key)


@pytest.mark.parametrize(('text','expected','evidence'), [
    ('Solar panels for Queensland Australia homeowners',False,[]),
    ('Trusted Queenslands installation and solar panel advice',False,[]),
    ('Regional service across Yorkshire England',False,[]),
    ('Brooklyn Park, Minnesota roofing company',False,[]),
    ('Bronxmania marketing platform',False,[]),
    ('Solar consultancy in Queens, Australia',False,[]),
    ('Contractor serving New York City permits',True,['new york city','new york']),
    ('Verified Manhattan and Queens, NY roofing service',True,['queens']),
    ('Residential solar service in NYC',True,['nyc']),
])
def test_first_party_borough_names_do_not_invent_nyc_territory(text,expected,evidence):
    state,hits=_nyc_territory_evidence({
        'title':'First Party Company Site',
        'description':text,
        'business_names':['Australian Solar Quotes'],
        'pages_checked':[{'visible_text':text}],
    })
    assert state is expected
    assert all(x in hits for x in evidence)
    if not expected:
        assert hits==[]


def test_nyc_territory_does_not_infer_from_url_only():
    state,hits=_nyc_territory_evidence({
        'title':'Queensland Solar Quotes',
        'description':'Get Australian solar pricing in Queensland',
        'canonical_url':'https://australiansolarquotes.com.au/',
        'pages_checked':[{'url':'https://australiansolarquotes.com.au/queensland'}],
    })
    assert state is False
    assert hits == []


def test_multimarket_scout_does_not_misroute_queensland_to_nyc(monkeypatch):
    from empire_os.buyer_acquisition_scout import run_buyer_scout

    monkeypatch.setattr(
        'empire_os.buyer_acquisition_scout.search_domains_parallel',
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        'empire_os.buyer_acquisition_scout.probe_site',
        lambda url, **kw: {
            'ok': True,
            'canonical_url': url,
            'final_url': url,
            'title': 'Australian Solar Quotes',
            'description': 'Independent solar referrals across Queensland, Australia',
            'business_names': ['Australian Solar Quotes'],
            'addresses': ['Brisbane Queensland, Australia'],
            'emails': [], 'phones': [], 'people': [],
            'pages_checked': [{
                'url': url,
                'visible_text': 'Queensland solar panel quotes in Australia',
            }],
            'evidence_score': 0.65,
        },
    )
    outcome = run_buyer_scout(
        {'priority_targets': [{
            'priority_score': 100,
            'research_queries': {
                'direct_demand_buyers': [
                    'solar referral programme Australia',
                ],
            },
        }]},
        max_queries=2, max_domains=10, max_probes=5,
        research_seed_records=[{
            'website': 'https://australiansolarquotes.com.au/',
            'domain': 'australiansolarquotes.com.au',
            'source_refs': [
                'public:multimarket_review:AU:australiansolarquotes.com.au',
            ],
            'target_markets': ['AU'],
            'target_buyer_pools': ['direct_demand_buyers'],
        }],
    )
    row = next(r for r in outcome['candidates']
               if r['domain'] == 'australiansolarquotes.com.au')
    assert row['permit_territory_state'] == 'NYC_NOT_OBSERVED'
    assert row['permit_territory_evidence'] == []
    assert row['canonical_identity_verified'] is False
    assert row['commercial_terms_verified'] is False
    assert row['outreach_authorized'] is False
    assert outcome['outbound_sent'] is False
    assert outcome['execution_authority'] == 'none'
