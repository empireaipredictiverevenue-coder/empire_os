from hashlib import sha256
import json
from empire_os.skillforge import catalogue

def test_skillforge_inventory_not_automatic_approval(tmp_path):
    p=tmp_path/'empire-reply-triage';p.mkdir();content=b'---\nlicense: internal\n---\n# Reply triage';(p/'SKILL.md').write_bytes(content)
    report=catalogue(root=tmp_path)
    assert report['skill_count']==1
    assert report['approved_count']==0
    assert report['skills'][0]['tasks']==['commercial_reply']
    assert report['execution_authority']=='none'

def test_skillforge_approval_requires_matching_digest(tmp_path):
    p=tmp_path/'empire-reply-triage';p.mkdir();content=b'---\nlicense: internal\n---\n# Reply triage';(p/'SKILL.md').write_bytes(content)
    reg=tmp_path/'registry.json'
    reg.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':{'empire-reply-triage':{'status':'approved','sha256':sha256(content).hexdigest()}}}))
    assert catalogue(root=tmp_path,registry_path=reg)['approved_count']==1
    (p/'SKILL.md').write_text('changed')
    assert catalogue(root=tmp_path,registry_path=reg)['approved_count']==0
