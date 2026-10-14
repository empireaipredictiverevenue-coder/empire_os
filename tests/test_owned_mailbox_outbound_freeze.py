"""No emails/auto-approvals until owned mailbox and sender are independently verified."""
from __future__ import annotations
import json
import pytest

from scripts import outbound_governor_worker as worker
from scripts import outbound_email as manual
from empire_os.outbound_provider import OutboundProviderError, send_with_resend


def test_legacy_resend_api_key_never_confers_live_readiness(monkeypatch):
    for key,value in {
        'RESEND_API_KEY':'re_dangerous_legacy_token',
        'EMPIRE_OUTBOUND_FROM':'Phil - Empire AI <phil@mail.empire-ai.co.uk>',
        'EMPIRE_REPLY_TO':'reply@mail.empire-ai.co.uk',
        'EMPIRE_FOUNDER_IMAP_HOST':'example.org',
        'EMPIRE_FOUNDER_IMAP_USER':'user@example.org',
        'EMPIRE_FOUNDER_IMAP_PASSWORD':'fake_value',
    }.items():
        monkeypatch.setenv(key,value)
    assert worker._provider_ready() is False


def test_guarded_execute_governor_degrades_to_observe_even_with_auto_flags(monkeypatch,capsys):
    monkeypatch.setenv('EMPIRE_OUTBOUND_AUTO_APPROVE','true')
    monkeypatch.setenv('EMPIRE_OUTBOUND_AUTO_SEND','true')
    monkeypatch.setenv('RESEND_API_KEY','re_fake_legacy_key')
    calls=[]
    def read_only_sender(method,args):
        calls.append(method)
        if method=='list_outbound_governor_work':
            return [{'intent_id':'00000000-0000-0000-0000-000000000001',
                     'status':'approved','updated_at':'2026-10-09T12:00:00Z'}]
        if method=='get_outbound_intent_review':
            return {'intent_id':'00000000-0000-0000-0000-000000000001',
                    'status':'approved','actual_revenue':False,
                    'channel':'email','recipient':'buyer@example.org',
                    'subject':'Question','body_text':'Hello unsubscribe 68 Wentbridge Road Bolton BL1 2QR UK',
                    'expires_at':'2027-01-01T00:00:00+00:00'}
        if method=='get_outbound_governor_context':
            return {'suppressed':False,'review_ready':True,'outreach_ready':True,
                    'bound_to_decision_maker':True,'contact_source':'official_site',
                    'contact_confidence':0.9,'company_score':99}
        raise AssertionError('no mutations accepted: '+method)
    monkeypatch.setattr(worker,'_sender_rpc',lambda:read_only_sender)
    monkeypatch.setattr(worker,'_approver_rpc',lambda: (_ for _ in ()).throw(AssertionError('approval forbidden')))
    monkeypatch.setattr(worker,'execute_governor_decision',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('send forbidden')))
    exit_code=worker.main(['--mode','GUARDED_EXECUTE','--execute','--limit','1'])
    output=json.loads(capsys.readouterr().out)
    assert exit_code==0
    assert output['execution_requested'] is True
    assert output['execute'] is False
    assert output['mode']=='OBSERVE'
    assert output['owned_mailbox_gate']=='CLOSED'
    assert output['fatal_error_count']==0
    assert not any('claim' in call or 'approve' in call or 'delivery' in call for call in calls)
    assert output['results'][0]['evaluation']['mutation_authorized'] is False


def test_manual_send_blocks_before_loading_db_or_claim(monkeypatch):
    monkeypatch.setenv('EMPIRE_OUTBOUND_SENDER_DSN','test_dsn')
    monkeypatch.setenv('RESEND_API_KEY','re_fake_legacy_token')
    monkeypatch.setattr(manual,'PostgresOutboundRpc',lambda *a,**k: (_ for _ in ()).throw(AssertionError('never construct rpc')))
    with pytest.raises(OutboundProviderError,match='manual email sending blocked'):
        manual.main(['00000000-0000-0000-0000-000000000001','--send'])


def test_real_resend_network_unavailable_even_with_api_key(monkeypatch):
    import sys
    monkeypatch.delitem(sys.modules,'resend',raising=False)
    with pytest.raises(OutboundProviderError,match='third-party email transport disabled'):
        send_with_resend({'_sender_address':'phil@mail.empire-ai.co.uk',
                          '_idempotency_key':'outbound/test','to':['buyer@example.org']},
                         api_key='re_valid_but_retired')
    assert 'resend' not in sys.modules


def test_legacy_lead_deliverer_resend_path_cannot_send_or_fake_success():
    # Compile only the isolated function: importing the historical legacy
    # module would try to initialize unrelated /root/feedback directories.
    import ast
    from pathlib import Path
    source=Path('empire_os/agents/lead_deliverer_agent.py').read_text()
    tree=ast.parse(source)
    matches=[node for node in tree.body if isinstance(node,ast.FunctionDef)
             and node.name=='send_email']
    assert len(matches)==1
    namespace={}
    isolated=ast.Module(body=matches,type_ignores=[])
    exec(compile(isolated,'legacy_send_guard.py','exec'),namespace)
    success,reason=namespace['send_email']('buyer@example.org','Example','Draft only')
    assert success is False
    assert reason=='owned_mailbox_outbound_disabled'
    assert not any(isinstance(node,ast.Call)
                   and isinstance(node.func,ast.Attribute)
                   and node.func.attr in ('post','urlopen','send','sendmail')
                   for node in ast.walk(matches[0]))
