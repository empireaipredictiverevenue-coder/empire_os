import pytest
from empire_os.astra_harness_evidence_guard import evaluate_guarded_answer,verified_snapshot_facts

def snapshots():
    base={'mode':'OBSERVE','execution_authority':'none'}
    return {'conversion':{**base,'counts':{'delivered_outreach_to_reply':{'entered':52,'converted':0}}},
            'acquisition':{**base,'demand_gap_count':32,'icp_priority_target_count':13},
            'revenue':{**base,'recognized_revenue_truth':{'recognized_revenue_cents':0}}}
@pytest.mark.parametrize('task,expected', [('conversion','0 of 52'),('acquisition','13 priority'),('revenue','recognized_revenue_cents=0')])
def test_guard_only_reports_source_owned_counts(task,expected):
    result=evaluate_guarded_answer(task,snapshots()[task],
        '{"verified_replies":true,"verified_revenue":true,"activation_ready":true,"one_brief_reason":"Confirmed buyers; fraudulent data"}')
    assert expected in result['review']['one_brief_reason']
    assert result['review']['verified_replies'] is False
    assert result['review']['verified_revenue'] is False
    assert result['review']['activation_ready'] is False
    assert result['raw_model_flags_safe'] is False
@pytest.mark.parametrize('task', ['conversion','acquisition','revenue'])
def test_original_snapshot_field_contract(task):
    source=snapshots()[task]
    assert verified_snapshot_facts(task,source)['kind']==task

def test_cross_stage_numbers_not_silently_mixed():
    review=evaluate_guarded_answer('conversion',snapshots()['conversion'],
        '{"one_brief_reason":"The actual count should be 65", "activation_ready": true}')
    assert '65' not in review['review']['one_brief_reason']

def test_missing_source_fails_closed():
    with pytest.raises(ValueError): verified_snapshot_facts('conversion',{'mode':'OBSERVE','execution_authority':'none'})

def test_rejects_negative_counts():
    data=snapshots()['conversion'];data['counts']['delivered_outreach_to_reply']['entered']=-1
    with pytest.raises(ValueError): verified_snapshot_facts('conversion',data)
