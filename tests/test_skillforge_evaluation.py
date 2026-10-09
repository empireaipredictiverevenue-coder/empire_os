from empire_os.skillforge_evaluation import evaluate_skill, compare_skill_versions

def test_current_empire_skill_passes_static_contract(tmp_path):
    p=tmp_path/'empire-sample';p.mkdir()
    (p/'SKILL.md').write_text('---\nlicense: Internal\n---\n# Skill\n## Evidence contract\nNo execution authority.')
    result=evaluate_skill('empire-sample',root=tmp_path)
    assert result['passed'] is True
    assert result['agent_quality_verified'] is False
    assert result['approved'] is False

def test_modified_skill_does_not_inherit_approval(tmp_path):
    report=compare_skill_versions('empire-sample',b'v1',b'v2')
    assert report['changed'] is True
    assert report['approval_carried_forward'] is False
    assert report['improved'] is None

def test_digest_mismatch_fails(tmp_path):
    p=tmp_path/'empire-sample';p.mkdir()
    (p/'SKILL.md').write_text('---\nlicense: Internal\n---\n## Evidence contract\nNo execution authority.')
    assert evaluate_skill('empire-sample',root=tmp_path,expected_sha256='0'*64)['passed'] is False
