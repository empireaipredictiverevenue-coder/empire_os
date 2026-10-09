"""Paired metrics are independent of agent execution and cannot confer trust."""
from hashlib import sha256
import json
import pytest
from empire_os.skillforge_benchmark import (
    score_holdout, score_holdout_file, HoldoutContractError,
)


def _out(decision, code):
    return {'decision':decision,'reason_code':code,'execution_authority':'none'}


def _suite():
    cases=[]
    for i in range(10):
        negative=i<3
        decision='block' if negative else 'allow'
        gold=_out(decision,'reason')
        baseline=_out('hold','wrong') if i in (0,3,4) else gold
        cases.append({
            'case_id': f'case_{i}', 'split':'holdout',
            'scenario':'negative' if negative else 'positive',
            'source_evidence_sha256':sha256(f'independent_case_{i}'.encode()).hexdigest(),
            'expected':gold,'baseline':baseline,'candidate':gold,
        })
    return {'schema_version':'empire.skillforge.holdout.v1','suite_id':'suite_v1',
            'skill_name':'empire-reply-triage','skill_sha256':'a'*64,'cases':cases}


def test_paired_numeric_improvement_is_not_promotion():
    report=score_holdout(_suite())
    assert report['case_count']==10
    assert report['negative_case_count']==3
    assert report['baseline_correct']==7
    assert report['candidate_correct']==10
    assert report['paired_wins']==3
    assert report['uplift']==0.3
    assert report['numeric_gate_pass'] is True
    assert report['independent_performance_verified'] is False
    assert report['eligible_for_auto_approval'] is False


def test_negative_case_regression_blocks_numeric_gate():
    suite=_suite()
    suite['cases'][0]['candidate']=_out('allow','wrong')
    report=score_holdout(suite)
    assert report['negative_case_failures']==1
    assert report['numeric_gate_pass'] is False


def test_candidate_regression_blocks_improvement_even_with_wins():
    suite=_suite()
    suite['cases'][6]['candidate']=_out('hold','wrong')
    assert score_holdout(suite)['paired_regressions']==1
    assert score_holdout(suite)['numeric_gate_pass'] is False


def test_untrusted_outbound_execution_rejected_before_scoring():
    suite=_suite()
    suite['cases'][1]['candidate']['outbound_executed']=True
    with pytest.raises(HoldoutContractError,match='invalid_or_authorized_outcome'):
        score_holdout(suite)


def test_duplicate_case_evidence_rejected():
    suite=_suite()
    suite['cases'][1]['source_evidence_sha256']=suite['cases'][0]['source_evidence_sha256']
    with pytest.raises(HoldoutContractError,match='duplicate_or_unverifiable_case'):
        score_holdout(suite)


def test_short_suite_is_numeric_fail_not_approval():
    suite=_suite()
    suite['cases']=suite['cases'][:3]
    assert score_holdout(suite)['numeric_gate_pass'] is False


def test_no_unlabelled_or_non_holdout_cases():
    suite=_suite()
    suite['cases'][0]['split']='training'
    with pytest.raises(HoldoutContractError,match='case_not_holdout'):
        score_holdout(suite)


def test_file_ingest_is_bounded_and_symlinks_fail(tmp_path):
    p=tmp_path/'suite.json'
    p.write_text(json.dumps(_suite()))
    assert score_holdout_file(p)['numeric_gate_pass'] is True
    link=tmp_path/'shortcut.json';link.symlink_to(p)
    with pytest.raises(HoldoutContractError,match='unsafe_suite_path'):
        score_holdout_file(link)
