from empire_os.strategic_growth_intelligence import score_strategy_candidate
from empire_os.strategic_growth_sources import candidate_from_market_capture


def test_market_capture_adapter_preserves_truth_and_unknowns():
    analysis={
        'identity':{'market_key':'uk-home-services','territory_key':'manchester','corridor_key':'roofing:manchester','product_key':'territory-seat'},
        'capture_stage':{'stage':'EXPAND'},
        'market_attractiveness':{'score':0.78},
        'defensibility':{'score':0.79},
        'expected_economics':{'expected_gross_profit_cents':500000,'risk_adjusted':{'confidence':0.8}},
        'moat_gaps':[
            {'dimension':'search_authority','observed_value':0.7},
            {'dimension':'partner_density','observed_value':0.7},
            {'dimension':'data_advantage','observed_value':0.9},
            {'dimension':'product_fit','observed_value':0.9},
        ],
        'evidence_refs':['market:1','buyer:1','outcome:1'],
        'expansion_blockers':[],
        'next_strategic_objective':{'objective':'review_adjacent_corridor_expansion'},
    }
    candidate=candidate_from_market_capture(analysis)
    assert candidate['strategy_type']=='geo_territory'
    assert candidate['expected_upside_cents']==500000
    assert candidate['estimated_external_cost_cents'] is None
    assert candidate['buyer_accessibility'] is None
    scored=score_strategy_candidate(candidate)
    assert scored['score'] is not None
    assert scored['execution_authority']=='none'
    assert scored['outreach_enabled'] is False
