import pytest

from empire_os.strategic_growth_intelligence import (
    build_strategy_portfolio,
    candidate_from_mapping,
    score_strategy_candidate,
    strategy_experiment_contract,
)


def _candidate(strategy_id='s1', **overrides):
    row={
        'strategy_id':strategy_id,
        'strategy_type':'zero_paid_acquisition',
        'thesis':'Capture roofing demand through AEO content and public intent signals.',
        'target_market':'roofing',
        'territory':'Dallas, TX',
        'target_icp':'regional roofing contractors',
        'target_roles':['owner','marketing director'],
        'channel':'seo_aeo_geo',
        'offer_key':'predictive_revenue_diagnostic',
        'evidence_refs':['search:roofing-dallas','signal:permit-intent'],
        'evidence_confidence':0.8,
        'expected_upside_cents':None,
        'estimated_external_cost_cents':0,
        'time_to_signal_days':14,
        'speed_to_signal':0.8,
        'reversibility':0.95,
        'strategic_fit':0.9,
        'product_market_fit':0.8,
        'buyer_accessibility':0.75,
        'data_advantage':0.9,
        'distribution_advantage':0.8,
        'competitive_gap':0.7,
        'learning_value':0.9,
        'moat_contribution':0.7,
        'operational_simplicity':0.8,
        'external_cost_efficiency':1.0,
        'dependencies':['search_intelligence'],
        'risks':['organic_signal_may_be_slow'],
        'experiment':{
            'hypothesis':'AEO landing pages increase qualified organic intent.',
            'baseline':'current observed search presence',
            'intervention':'publish evidence-backed answer pages after review',
            'target_metric':'qualified organic conversations',
            'measurement_window':'30 days',
            'minimum_evidence_threshold':'10 observed qualified sessions',
            'expected_learning':'which query clusters create buyer intent',
        },
        'kill_criteria':['no qualified signal after 30 days'],
        'owner_department':'marketing',
        'authority_required':'observe',
    }
    row.update(overrides)
    return row


def test_candidate_requires_real_evidence_and_supported_type():
    with pytest.raises(ValueError, match='evidence_refs'):
        candidate_from_mapping(_candidate(evidence_refs=[]))
    with pytest.raises(ValueError, match='unsupported strategy_type'):
        candidate_from_mapping(_candidate(strategy_type='magic_growth'))


def test_strategy_score_uses_only_observed_dimensions_and_keeps_unknown_economics_unknown():
    result=score_strategy_candidate(_candidate(expected_upside_cents=None))
    assert result['score'] is not None
    assert result['economics_observed'] is False
    assert result['candidate']['expected_upside_cents'] is None
    assert result['candidate']['estimated_external_cost_cents']==0
    assert result['execution_authority']=='none'
    assert result['outreach_enabled'] is False
    assert result['spend_enabled'] is False


def test_missing_evidence_confidence_blocks_ranking_without_fabricating_score():
    result=score_strategy_candidate(_candidate(evidence_confidence=None))
    assert result['dimension_score'] is not None
    assert result['score'] is None
    assert result['evidence_complete_for_ranking'] is False


def test_experiment_contract_is_review_only_and_requires_measurement_fields():
    good=strategy_experiment_contract(_candidate())
    assert good['review_ready'] is True
    assert good['automatic_external_execution'] is False
    assert good['execution_authority']=='none'

    bad=_candidate(experiment={'hypothesis':'test'})
    result=strategy_experiment_contract(bad)
    assert result['review_ready'] is False
    assert 'experiment_target_metric_required' in result['blockers']


def test_portfolio_deduplicates_same_strategy_even_with_new_id():
    a=_candidate('s1')
    b=_candidate('s2')
    portfolio=build_strategy_portfolio([a,b])
    assert portfolio['candidate_count']==1
    assert portfolio['selected_count']==1
    assert portfolio['duplicate_strategy_ids']==['s2']


def test_portfolio_diversifies_strategy_types_and_channels():
    rows=[
        _candidate('s1'),
        _candidate('s2', thesis='Organic AEO cluster two', territory='Austin, TX'),
        _candidate('s3', thesis='Organic AEO cluster three', territory='Phoenix, AZ'),
        _candidate('s4', strategy_type='partnership_affiliate', channel='partnerships', thesis='Partner with roofing software ecosystems.', territory='US'),
    ]
    portfolio=build_strategy_portfolio(rows,max_per_strategy_type=2,max_per_channel=2,limit=4)
    assert portfolio['selected_count']==3
    blockers=[b for item in portfolio['deferred'] for b in item['portfolio_blockers']]
    assert 'strategy_type_concentration_limit' in blockers or 'channel_concentration_limit' in blockers
    assert portfolio['automatic_external_execution'] is False


def test_portfolio_economic_upside_is_relative_only_when_observed():
    low=_candidate('low', thesis='Low evidenced upside strategy', territory='Austin, TX', expected_upside_cents=10000)
    high=_candidate('high', thesis='High evidenced upside strategy', territory='Houston, TX', expected_upside_cents=100000)
    unknown=_candidate('unknown', thesis='Unknown economics strategy', territory='Denver, CO', expected_upside_cents=None)
    portfolio=build_strategy_portfolio([low,high,unknown],max_per_strategy_type=5,max_per_channel=5)
    by_id={item['candidate']['strategy_id']:item for item in portfolio['selected']}
    assert by_id['high']['relative_upside_score']==1.0
    assert by_id['low']['relative_upside_score']==0.1
    assert by_id['unknown']['relative_upside_score'] is None
    assert by_id['unknown']['candidate']['expected_upside_cents'] is None


def test_persona_targeting_is_role_based_and_does_not_enable_contact_execution():
    result=score_strategy_candidate(_candidate(strategy_type='persona_buying_committee',target_roles=['CEO','Head of Growth']))
    assert result['candidate']['target_roles']==('CEO','Head of Growth')
    assert result['outreach_enabled'] is False
    assert result['execution_authority']=='none'
