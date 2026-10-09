from empire_os.skill_review import review_local_skill

def test_proprietary_skill_requires_review(tmp_path):
    p=tmp_path/'docx';p.mkdir();(p/'SKILL.md').write_text('---\nlicense: Proprietary. LICENSE.txt has complete terms\n---')
    result=review_local_skill('docx',root=tmp_path)
    assert 'proprietary_license_requires_review' in result['reasons']
    assert result['approved'] is False

def test_third_party_brand_detected(tmp_path):
    p=tmp_path/'brand-guidelines';p.mkdir();(p/'SKILL.md').write_text('---\nlicense: MIT\n---\nUse Anthropic brand colors')
    assert 'third_party_brand_instructions' in review_local_skill('brand-guidelines',root=tmp_path)['reasons']

def test_unknown_license_does_not_autoapprove(tmp_path):
    p=tmp_path/'internal-comms';p.mkdir();(p/'SKILL.md').write_text('general guidance')
    result=review_local_skill('internal-comms',root=tmp_path)
    assert result['approved'] is False
    assert 'license_not_declared' in result['reasons']
