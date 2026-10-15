"""Sovereign, cross-border publisher/lead-buyer research via existing scout."""
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.buyer_public_research_seed import (
    build_public_research_seeds, publisher_review_page_path,
)
from empire_os.buyer_acquisition_scout import select_market_review_domains
from empire_os.buyer_network_research_rotation import accepted_domain

NOW = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)


def candidates(at=NOW, search=None):
    return build_public_research_seeds(
        {}, search_fn=search or (lambda queries, num: {}),
        max_queries=2, results_per_query=5, include_volume=False,
        observed_at=at,
    )


def test_official_programme_candidates_cover_four_markets_without_granting_any_terms():
    data=candidates()
    assert data['multimarket_first_party_seed_count'] == 9
    assert data['markets_targeted'] == ['AU','CA','UK','USA']
    assert data['searches_per_existing_cycle_unchanged'] is True
    assert data['query_count'] == 2
    assert data['fresh_search_domain_count'] == 0
    assert data['fresh_search_result_status'] == 'NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED'
    assert data['outbound_sent'] is False
    assert data['database_write_performed'] is False
    assert data['commercial_authority'] == 'none'
    by_domain={row['domain']:row for row in data['seeds']}
    expected={
        'modernize.com':'USA',
        'angi.com':'USA',
        'homeservicesleadgroup.com':'USA',
        'leads2trade.co.uk':'UK',
        'yoursolarquotes.com.au':'AU',
        'australiansolarquotes.com.au':'AU',
        'liveleads.ca':'CA',
        'centfix.ca':'CA',
        'xolar.ca':'CA',
    }
    for domain,market in expected.items():
        row=by_domain[domain]
        assert row['target_markets'] == [market]
        assert row['target_verticals']
        assert f'public:multimarket_review:{market}:{domain}' in row['source_refs']
        assert row['truth_class'] == 'OBSERVED_PUBLIC_RESEARCH'
        assert row['identity_verified'] is False
        assert row['buyer_capacity_verified'] is False
        assert row['buyer_price_verified'] is False
        assert row['commercial_terms_verified'] is False
        assert row['outreach_authorized'] is False
        assert row['execution_authority'] == 'none'
    assert accepted_domain('yoursolarquotes.com.au') is True
    assert accepted_domain('australiansolarquotes.com.au') is True


def test_bounded_searches_rotate_all_markets_on_original_30_min_cadence():
    witnessed=[]
    for cycle in range(6):
        when=NOW+timedelta(minutes=30*cycle)
        def capture(queries,num):
            assert len(queries)==2
            assert num==5
            witnessed.extend(queries)
            return {q:['candidate.example'] for q in queries}
        result=candidates(when,capture)
        assert result['query_count']==2
        assert result['query_strategy_counts']['publisher_first']==2
        assert result['fresh_search_result_status']=='FRESH_DOMAIN_RESULTS_OBSERVED'
        assert result['outbound_sent'] is False
    assert len(witnessed)==12
    assert len(set(witnessed))==12
    assert any('United States' in q for q in witnessed)
    assert any('United Kingdom' in q or '"UK"' in q for q in witnessed)
    assert any('Australia' in q for q in witnessed)
    assert any('Canada' in q for q in witnessed)


def test_existing_first_party_probe_finds_actual_country_specific_entry_paths():
    expected={
       'modernize.com':'/affiliates',
       'leads2trade.co.uk':'/about/affiliates',
       'yoursolarquotes.com.au':'/solar-affiliate-program',
       'centfix.ca':'/affiliates',
       'xolar.ca':'/referral-program',
       'australiansolarquotes.com.au':'/about-us/referral-partners',
    }
    for domain,path in expected.items():
        assert publisher_review_page_path(domain)==path


def test_market_review_slots_fair_and_bounded_even_with_many_existing_us_seeds():
    domain_map={**{f'usa{i}.com':'USA' for i in range(8)},
                'ukbuyer.co.uk':'UK', 'australia.com.au':'AU',
                'canadabuyer.ca':'CA', 'legacy.example':'UNSPECIFIED'}
    observations=[]
    for n in range(5):
        reviewed=select_market_review_domains(domain_map,slots=4,
            as_of=NOW+timedelta(minutes=30*n))
        assert len(reviewed)==4
        assert len(set(reviewed))==4
        observations.extend(domain_map[x] for x in reviewed)
    assert set(observations)>={'USA','UK','AU','CA','UNSPECIFIED'}
    assert select_market_review_domains(domain_map,slots=0,as_of=NOW)==[]
    assert len(select_market_review_domains(domain_map,slots=999,as_of=NOW))==4


def test_one_slot_rotates_market_instead_of_permanently_favouring_usa():
    market={'company.com':'USA','company.co.uk':'UK','company.com.au':'AU','company.ca':'CA'}
    selected=[select_market_review_domains(market,slots=1,
              as_of=NOW+timedelta(minutes=30*i))[0] for i in range(4)]
    assert len(set(selected))==4


def test_naive_market_rotation_refused():
    with pytest.raises(ValueError):
        select_market_review_domains({'a.com':'USA'},slots=1,
             as_of=datetime(2026,10,15))


def test_real_scout_reserves_bounded_multimarket_review_probes(monkeypatch):
    from empire_os.buyer_acquisition_scout import run_buyer_scout
    from scripts.probe_buyer_network_direct_sites import valid_domain

    seeds=candidates()['seeds']
    assert valid_domain('yoursolarquotes.com.au') is True
    assert valid_domain('centfix.ca') is True
    assert valid_domain('nope.invalid') is False
    monkeypatch.setattr('empire_os.buyer_acquisition_scout.search_domains_parallel',
        lambda queries,num:{query:[f'roofing{i:03d}.com' for i in range(50)]
                            for query in queries})
    probed=[]
    def fake_probe(url,**kwargs):
        probed.append(url)
        return {'ok':True,'canonical_url':url,'final_url':url,
                'title':'Programme Research','description':'Publisher opportunity',
                'business_names':[],'emails':[],'phones':[],
                'people':[],'pages_checked':[],'evidence_score':0.15}
    monkeypatch.setattr('empire_os.buyer_acquisition_scout.probe_site',fake_probe)
    research_plan={'priority_targets':[{
        'priority_score':100,
        'corridor_key':'corridor:v1:roofing:austin_tx:qualified_lead:lead',
        'opportunity_key':'market:roofing:austin_tx',
        'research_queries':{'direct_demand_buyers':['"buy roofing leads" austin tx']},
    }]}
    report=run_buyer_scout(research_plan,max_queries=5,max_domains=40,
                           max_probes=20,research_seed_records=seeds)
    assert report['publisher_review_seed_count'] >= 9
    assert report['publisher_review_included_count'] == 4
    assert report['publisher_review_probed_count'] == 4
    assert len(report['candidates']) <= 40
    assert len(probed) <= 20
    included={r['domain'] for r in report['candidates'] if r['domain'] in {
        'modernize.com','angi.com','homeservicesleadgroup.com',
        'leads2trade.co.uk','yoursolarquotes.com.au',
        'australiansolarquotes.com.au','liveleads.ca','centfix.ca','xolar.ca'
    }}
    assert len(included) >= 3
    assert any('.com.au' in x or '.ca' in x or '.co.uk' in x for x in included)
    assert report['publisher_review_claims_are_not_buyer_approval'] is True
    assert report['outbound_sent'] is False
    assert report['execution_authority'] == 'none'
    assert all(r['commercial_terms_verified'] is False and
               r['outreach_authorized'] is False
               for r in report['candidates'] if r['domain'] in included)


def test_installed_scout_domain_budget_rotates_three_slots_across_all_countries():
    entries={
        'modernize.com':'USA', 'angi.com':'USA',
        'leads2trade.co.uk':'UK', 'yoursolarquotes.com.au':'AU',
        'centfix.ca':'CA',
    }
    across=set()
    for i in range(5):
        chosen=select_market_review_domains(entries,slots=min(4,30//8,len(entries)),
            as_of=NOW+timedelta(minutes=30*i))
        assert len(chosen)==3
        assert len(set(chosen))==3
        across.update(entries[x] for x in chosen)
    assert across=={'USA','UK','AU','CA'}


def test_market_queries_always_preserve_user_consent_and_no_click_payment_claim():
    x=candidates()
    assert all(s['buyer_capacity_verified'] is False for s in x['seeds'])
    assert all(s['commercial_terms_verified'] is False for s in x['seeds'])
    assert all(s['outreach_authorized'] is False for s in x['seeds'])
    assert 'published_cpc_rate' not in str(x)
    assert x['search_provider_health_independently_verified'] is False
