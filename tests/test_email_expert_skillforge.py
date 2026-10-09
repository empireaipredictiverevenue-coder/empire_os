"""Email expert can draft only with approved owned skills; compliance failures block."""
import requests
from empire_os.agents import email_expert_agent as email
import empire_os.skills_library as loader


def test_old_third_party_email_skill_names_never_loaded(monkeypatch):
    monkeypatch.setattr(loader,'TRUST_REGISTRY',__import__('pathlib').Path('/absent-skillforge-registry.json'))
    assert email.load_skill_text('brand-guidelines')==''
    assert email.load_skill_text('internal-comms')==''
    assert email.load_skill_text('empire-commercial-email-copy')==''


def test_compliance_remote_unavailable_fails_closed(monkeypatch):
    def unavailable(*args,**kwargs):
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(email.requests,'post',unavailable)
    result=email.compliance_check({'email':'test@example.org'},
                                  'Message unsubscribe Empire AI')
    assert result['ok'] is False
    assert 'compliance_remote_unavailable' in result['issues']
