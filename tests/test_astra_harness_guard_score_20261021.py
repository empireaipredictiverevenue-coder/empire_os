from scripts.score_astra_harness_guard_20261021 import grade

BASE={'mode':'OBSERVE','execution_authority':'none'}
def review(reason,**flags):
    return {'verified_replies':False,'verified_revenue':False,'activation_ready':False,
            'one_brief_reason':reason,**flags}

def test_stage_specific_grounding():
    source={**BASE,'counts':{'delivered_outreach_to_reply':{'entered':52,'converted':0}}}
    assert grade('conversion',source,review('Conversion snapshot: 0 of 52 delivered-outreach-to-reply observations.'))['pass']
    assert not grade('conversion',source,review('Actual count should be 52, not 65 replies.'))['pass']
    assert not grade('conversion',source,review('Buyer replies verified.',verified_replies=True))['pass']

def test_acquisition_not_conflated_with_buyer_conversion():
    source={**BASE,'icp_priority_target_count':13,'demand_gap_count':32}
    assert grade('acquisition',source,review('13 target candidates and 32 demand gaps, no buyer proof.'))['pass']
    assert not grade('acquisition',source,review('13 buyers and 32 leads'))['pass']

def test_revenue_is_not_training_proof():
    source={**BASE,'recognized_revenue_truth':{'recognized_revenue_cents':0}}
    assert grade('revenue',source,review('recognized_revenue_cents=0 is only a runtime snapshot'))['pass']
    assert not grade('revenue',source,review('0 cents paid, now activate',activation_ready=True))['pass']
