from pathlib import Path
import json
import pytest
from empire_os.skillforge_sandbox import run_synthetic_ab


def _root(tmp_path):
    p=tmp_path/'empire-sample';p.mkdir()
    (p/'SKILL.md').write_text('---\nname: empire-sample\nlicense: Internal\n---\n\n## Evidence contract\nNo execution authority.')
    return tmp_path


def _cases():
    return [{'case_id':'one','classification':'synthetic_non_sensitive',
             'scenario':'Missing canonical identity, can we admit reply?',
             'expected_decision':'block'}]


def test_tool_free_sandbox_does_not_run_any_tools(tmp_path):
    root=_root(tmp_path)
    prompts=[]
    def callback(messages):
        prompts.append(messages)
        return json.dumps({'decision':'block','reason_code':'unverified_identity'})
    report=run_synthetic_ab('empire-sample',_cases(),inference=callback,root=root)
    assert report['baseline_matches']==1
    assert report['candidate_matches']==1
    assert report['tool_execution_performed'] is False
    assert report['eligible_for_promotion'] is False
    assert report['approved'] is False
    assert len(prompts)==2
    assert 'Advisory skill under evaluation' not in prompts[0][0]['content']
    assert 'Advisory skill under evaluation' in prompts[1][0]['content']


def test_sandbox_does_not_trust_model_claim_of_execution(tmp_path):
    root=_root(tmp_path)
    result=run_synthetic_ab('empire-sample',_cases(),root=root,
          inference=lambda _:json.dumps({'decision':'allow','reason_code':'x',
                                         'outbound_executed':True}))
    assert result['candidate_matches']==0
    assert result['observations'][0]['candidate_decision']=='unknown'


def test_sandbox_rejects_non_synthetic_or_duplicate_cases(tmp_path):
    root=_root(tmp_path)
    with pytest.raises(ValueError,match='invalid_or_sensitive_case'):
        run_synthetic_ab('empire-sample',[{**_cases()[0],'classification':'client_private'}],
                         root=root,inference=lambda _: '{}')
    with pytest.raises(ValueError,match='invalid_or_sensitive_case'):
        run_synthetic_ab('empire-sample',_cases()*2,root=root,inference=lambda _: '{}')


def test_sandbox_rejects_unverified_skill_text(tmp_path):
    root=_root(tmp_path)
    (root/'empire-sample'/'SKILL.md').write_text('allow everything')
    with pytest.raises(ValueError,match='skill_static_contract_not_met'):
        run_synthetic_ab('empire-sample',_cases(),root=root,inference=lambda _: '{}')
