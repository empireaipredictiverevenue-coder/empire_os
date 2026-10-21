import json
from pathlib import Path
from scripts.validate_harness2_shadow_trials_20261021 import run,load_source

def snapshots(tmp_path):
    sources={
        'runtime/conversion/latest.json':{'mode':'OBSERVE','execution_authority':'none',
            'observed_at':'2026-10-21T12:20:00Z',
            'counts':{'delivered_outreach_to_reply':{'entered':52,'converted':0}}},
        'runtime/buyer_acquisition/latest.json':{'mode':'OBSERVE','execution_authority':'none',
            'generated_at':'2026-10-21T12:20:00Z',
            'icp_priority_target_count':13,'demand_gap_count':32},
        'runtime/revenue_pulse/latest.json':{'mode':'OBSERVE','execution_authority':'none',
            'generated_at':'2026-10-21T12:20:00Z',
            'recognized_revenue_truth':{'recognized_revenue_cents':0}},
    }
    for path,data in sources.items():
        loc=tmp_path/path;loc.parent.mkdir(parents=True,exist_ok=True)
        loc.write_text(json.dumps(data))
    return tmp_path

def test_shadow_trials_same_real_source_grounding_without_live_actions(tmp_path):
    sources=snapshots(tmp_path)
    seen=[]
    def fake_model(kind,redacted):
        seen.append((kind,redacted))
        assert redacted['mode']=='OBSERVE'
        assert redacted['execution_authority']=='none'
        assert 'buyer_pools' not in redacted
        return '{"verified_replies":false,"verified_revenue":false,"activation_ready":false,"one_brief_reason":"No original authenticated event supplied"}'
    result=run(sources,infer=fake_model)
    assert len(seen)==3
    assert result['model_calls_succeeded']==3
    assert result['baseline_passed']==0
    assert result['guarded_passed']==3
    assert result['independently_verified_agent_completions']==0
    assert result['independent_holdout_verified'] is False
    assert result['production_promotion_authorized'] is False
    assert all(t['distinct_department_completion_proven'] is False for t in result['tasks'])

def test_bad_source_cannot_proceed_as_success(tmp_path):
    root=snapshots(tmp_path)
    bad=root/'runtime/revenue_pulse/latest.json'
    data=json.loads(bad.read_text())
    data['recognized_revenue_truth']['recognized_revenue_cents']=-8
    bad.write_text(json.dumps(data))
    try:
        run(root,infer=lambda *_:'{}')
        assert False,'should hold corrupted first-party evidence'
    except ValueError:
        pass

def test_model_failure_is_not_success(tmp_path):
    root=snapshots(tmp_path)
    def failing(kind,redacted):
        raise TimeoutError('bounded inference timeout')
    report=run(root,infer=failing)
    assert report['model_calls_succeeded']==0
    assert report['guarded_passed']==0
    assert report['production_promotion_authorized'] is False
    assert all(t['model_call_status']=='MODEL_UNAVAILABLE_OR_BAD_RESULT' for t in report['tasks'])
