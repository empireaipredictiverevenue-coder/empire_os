import json
from pathlib import Path
from empire_os.astra_department_dispatch import dispatch_executive_plan

def test_dispatch_includes_skill_advice_without_execution_authority(tmp_path):
    source = tmp_path / 'runtime/astra/executive_latest.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'plan_id': 'test-skill-plan', 'plan': [{
        'step_id': 'skill-step-1', 'goal_key': 'test', 'department_keys': ['sales'],
        'target_component': 'reply_audit', 'action': 'inspect', 'authority': 'observe',
        'auto_dispatch_eligible': True, 'founder_gate_required': False,
    }]}))
    report = dispatch_executive_plan(tmp_path)
    assert report['execution_authority'] == 'none'
    assert report['external_execution_performed'] is False
    assert report['queued_count'] == 1
    advice = report['items'][0]['skill_advice']
    assert advice['execution_authority'] == 'none'
    assert advice['skill_recommendations'][0]['department'] == 'sales'
    assert advice['queue_mutated'] is False
