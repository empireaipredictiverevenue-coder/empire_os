from hashlib import sha256
import json
from empire_os.skillforge_promotion import promotion_preflight


def _skill(tmp_path):
    folder=tmp_path/'empire-sample';folder.mkdir()
    text='---\nlicense: Internal\n---\n\n## Evidence contract\nNo execution authority granted.'
    (folder/'SKILL.md').write_text(text)
    return sha256(text.encode()).hexdigest()


def _suite(digest):
    cases=[]
    for i in range(10):
        gold={'decision':'block' if i<3 else 'allow','reason_code':'verified','execution_authority':'none'}
        baseline=dict(gold)
        if i in (0,3,4):
            baseline={'decision':'hold','reason_code':'unknown','execution_authority':'none'}
        cases.append({'case_id':f'case_{i}','split':'holdout',
                      'scenario':'negative' if i<3 else 'positive',
                      'source_evidence_sha256':sha256(f'case_{i}'.encode()).hexdigest(),
                      'expected':gold,'baseline':baseline,'candidate':gold})
    return {'schema_version':'empire.skillforge.holdout.v1','suite_id':'vetted_suite',
            'skill_name':'empire-sample','skill_sha256':digest,'cases':cases}


def test_missing_holdout_blocks_promotion(tmp_path):
    _skill(tmp_path)
    plan=promotion_preflight('empire-sample',root=tmp_path)
    assert plan['status']=='BLOCKED'
    assert 'independently_labelled_holdout_not_supplied' in plan['blocks']
    assert plan['promoted'] is False


def test_good_offline_scores_still_cannot_approve(tmp_path):
    digest=_skill(tmp_path)
    plan=promotion_preflight('empire-sample',root=tmp_path,suite=_suite(digest))
    assert plan['status']=='READY_FOR_INDEPENDENT_REVIEW'
    assert plan['benchmark']['numeric_gate_pass'] is True
    assert plan['founder_approval_recorded'] is False
    assert plan['independent_performance_verified'] is False
    assert plan['trust_registry_changed'] is False
    assert plan['promoted'] is False
    assert plan['required_reviews']


def test_benchmark_for_different_skill_digest_is_blocked(tmp_path):
    _skill(tmp_path)
    result=promotion_preflight('empire-sample',root=tmp_path,suite=_suite('f'*64))
    assert result['status']=='BLOCKED'
    assert 'benchmark_skill_identity_or_digest_mismatch' in result['blocks']


def test_existing_manual_registry_approval_does_not_waive_evaluation(tmp_path):
    digest=_skill(tmp_path)
    registry=tmp_path/'registry.json'
    registry.write_text(json.dumps({'schema_version':'empire.skill_trust.v1',
                                     'approved_skills':{'empire-sample':{'status':'approved','sha256':digest}}}))
    plan=promotion_preflight('empire-sample',root=tmp_path,trust_registry=registry)
    assert plan['already_approved_in_registry'] is True
    assert plan['status']=='BLOCKED'
    assert plan['promoted'] is False


def test_local_skill_change_invalidates_previous_holdout(tmp_path):
    digest=_skill(tmp_path)
    suite=_suite(digest)
    (tmp_path/'empire-sample'/'SKILL.md').write_text('changed contract')
    result=promotion_preflight('empire-sample',root=tmp_path,suite=suite)
    assert result['status']=='BLOCKED'
    assert 'benchmark_skill_identity_or_digest_mismatch' in result['blocks']
