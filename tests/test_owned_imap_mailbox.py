"""Owner-operated inbox: TLS/read-only/UID stability/no SaaS fallback."""
from __future__ import annotations

from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
import ssl
import pytest

from empire_os.owned_imap_mailbox import (
    OwnedIMAPMailboxProvider, MailboxReadUnavailable,
)
from empire_os.founder_mailbox_api import create_founder_mailbox_router


def wire_message(*, sent: bool = False) -> bytes:
    item = EmailMessage()
    item['Message-ID'] = '<provider-msg-unique@example.org>'
    item['Date'] = format_datetime(datetime(2026,10,9,12,0,tzinfo=timezone.utc))
    item['From'] = 'phil@mail.empire-ai.co.uk' if sent else 'buyer@example.org'
    item['To'] = 'buyer@example.org' if sent else 'reply+11111111-2222-3333-4444-555555555555@mail.empire-ai.co.uk'
    item['Subject'] = 'Pilot' if sent else 'Re: Pilot'
    item.set_content('Pilot details sent.' if sent else 'Can you send the details?')
    return item.as_bytes()


class FakeIMAP:
    def __init__(self, *, sent: bool, valid: bool = True):
        self.calls=[]
        self.sent=sent
        self.valid=valid

    def login(self, user, password):
        self.calls.append(('LOGIN', bool(user),bool(password)))
        return 'OK',[b'OK']

    def select(self, folder, *, readonly=False):
        self.calls.append(('SELECT',folder,readonly))
        return 'OK',[b'2']

    def response(self,name):
        self.calls.append(('RESPONSE',name))
        return ('UIDVALIDITY',[b'77']) if self.valid else (None,[None])

    def uid(self, verb, *arguments):
        self.calls.append(('UID', verb,arguments))
        if verb == 'SEARCH':
            return 'OK',[b'12 13']
        if verb == 'FETCH':
            assert arguments[1]=='(BODY.PEEK[]<0.32768>)'
            return 'OK',[(b'13 (BODY[] {100}',wire_message(sent=self.sent)),b')']
        raise AssertionError('IMAP mutation or unsupported command')

    def logout(self):
        self.calls.append(('LOGOUT',))
        return 'BYE',[b'BYE']


def provider_factory(*, sent: bool = False, valid: bool = True):
    sessions=[]
    def factory(host, port, *, ssl_context, timeout):
        assert host=='mail.empire-ai.co.uk'
        assert port==993
        assert isinstance(ssl_context,ssl.SSLContext)
        assert ssl_context.verify_mode==ssl.CERT_REQUIRED
        assert timeout <= 8
        session=FakeIMAP(sent=sent,valid=valid)
        sessions.append(session)
        return session
    p=OwnedIMAPMailboxProvider(host='mail.empire-ai.co.uk', username='phil@mail.empire-ai.co.uk',
                               password='not_a_real_secret',client_factory=factory)
    return p,sessions


def test_read_only_uid_bounded_lookup_preserves_actual_message_id():
    provider,sessions=provider_factory()
    messages=provider.list_received(limit=1)
    assert len(messages)==1
    row=messages[0]
    assert row['id']=='imap:inbox:77:13'
    assert row['message_id']=='<provider-msg-unique@example.org>'
    assert row['canonical_contact_identity_verified'] is False
    assert row['canonical_thread_identity_verified'] is False
    assert row['text'].startswith('Can you')
    assert provider.suppression_evidence_complete is False
    assert all(call[0] in ('LOGIN','SELECT','RESPONSE','UID','LOGOUT') for call in sessions[0].calls)
    assert ('SELECT','"INBOX"',True) in sessions[0].calls
    assert all(call[1] not in ('STORE','EXPUNGE','APPEND','COPY','DELETE')
               for call in sessions[0].calls if call[0]=='UID')
    assert sessions[0].calls[-1]==('LOGOUT',)


def test_sent_reads_only_explicit_folder_and_stable_uid():
    provider,sessions=provider_factory(sent=True)
    result=provider.list_sent(limit=1)
    assert result[0]['id']=='imap:sent:77:13'
    assert result[0]['status']=='sent'
    assert ('SELECT','"Sent"',True) in sessions[0].calls
    assert provider.get_sent('imap:sent:77:13')['message_id']=='<provider-msg-unique@example.org>'


def test_uidvalidity_required_and_cross_folder_id_is_rejected():
    provider,_=provider_factory(valid=False)
    with pytest.raises(MailboxReadUnavailable,match='UIDVALIDITY_MISSING'):
        provider.list_received(limit=1)
    provider,_=provider_factory()
    with pytest.raises(MailboxReadUnavailable,match='MESSAGE_ID_MISMATCH'):
        provider.get_received('imap:sent:77:13')
    with pytest.raises(MailboxReadUnavailable,match='MESSAGE_ID_MISMATCH'):
        provider.get_received('imap:inbox:76:13')
    with pytest.raises(MailboxReadUnavailable,match='MESSAGE_ID_MISMATCH'):
        provider.get_received('../../../etc/passwd')


def test_no_credentials_is_fail_closed_and_does_not_open_network(monkeypatch):
    for key in ('EMPIRE_FOUNDER_IMAP_HOST','EMPIRE_FOUNDER_IMAP_USER',
                'EMPIRE_FOUNDER_IMAP_PASSWORD'):
        monkeypatch.delenv(key,raising=False)
    p=OwnedIMAPMailboxProvider()
    assert p.readiness()['configured'] is False
    with pytest.raises(MailboxReadUnavailable,match='CONFIGURATION_INCOMPLETE'):
        p.list_received(limit=1)


def test_imap_failure_sanitizes_sensitive_errors():
    def bad(host,port,*,ssl_context,timeout):
        raise OSError('credential SECRET_ABC and buyer@example.org')
    p=OwnedIMAPMailboxProvider(host='mail.empire-ai.co.uk', username='phil@mail.empire-ai.co.uk',
                               password='SECRET_ABC',client_factory=bad)
    with pytest.raises(MailboxReadUnavailable) as err:
        p.list_received(limit=1)
    assert str(err.value)=='OWN_IMAP_TLS_AUTH_UNAVAILABLE'


def test_founder_mailbox_owned_imap_never_promotes_message_or_allows_draft():
    own,_=provider_factory()
    app=FastAPI();app.include_router(create_founder_mailbox_router(own))
    client=TestClient(app)
    status=client.get('/v1/founder-mailbox/readiness').json()
    assert status['configured'] is True
    assert status['canonical_identity_verified'] is False
    assert status['suppression_evidence_complete'] is False
    response=client.get('/v1/founder-mailbox/threads',params={'limit':1})
    assert response.status_code==200
    mailbox=response.json()
    assert mailbox['provider']=='owned_imap'
    assert mailbox['canonical_buyer_conversation_verified'] is False
    assert mailbox['summary']['verified_canonical_buyer_replies']==0
    assert mailbox['suppression_evidence_complete'] is False
    for item in mailbox['threads']:
        assert item['canonical_identity_verified'] is False
        assert item['provider_message_only'] is True
        detail=client.get('/v1/founder-mailbox/threads/'+item['thread_id'])
        assert detail.status_code==200
        assert all(e['message_id'] is None for e in detail.json()['events'])
        draft=client.get('/v1/founder-mailbox/draft-preview',params={'thread_id':item['thread_id']})
        assert draft.status_code==409
        assert draft.json()['detail']=='suppression_evidence_not_verified'


def test_default_no_longer_instantiates_resend_without_approval(monkeypatch):
    for key in ('EMPIRE_FOUNDER_IMAP_HOST','EMPIRE_FOUNDER_IMAP_USER',
                'EMPIRE_FOUNDER_IMAP_PASSWORD','EMPIRE_FOUNDER_MAILBOX_PROVIDER'):
        monkeypatch.delenv(key,raising=False)
    app=FastAPI();app.include_router(create_founder_mailbox_router())
    client=TestClient(app)
    assert client.get('/v1/founder-mailbox/readiness').json()['status']=='NOT_CONFIGURED'
    result=client.get('/v1/founder-mailbox/summary')
    assert result.status_code==503
    assert 'MailboxReadUnavailable' in result.json()['detail']
    monkeypatch.setenv('EMPIRE_FOUNDER_MAILBOX_PROVIDER','resend')
    with pytest.raises(RuntimeError,match='PROVIDER_NOT_AUTHORIZED'):
        create_founder_mailbox_router()


def test_malformed_port_does_not_crash_founder_router(monkeypatch):
    monkeypatch.setenv('EMPIRE_FOUNDER_IMAP_PORT','not-a-port')
    monkeypatch.setenv('EMPIRE_FOUNDER_IMAP_HOST','mail.empire-ai.co.uk')
    monkeypatch.setenv('EMPIRE_FOUNDER_IMAP_USER','phil@mail.empire-ai.co.uk')
    monkeypatch.setenv('EMPIRE_FOUNDER_IMAP_PASSWORD','dummy_not_real')
    app=FastAPI();app.include_router(create_founder_mailbox_router())
    readiness=TestClient(app).get('/v1/founder-mailbox/readiness').json()
    assert readiness['status']=='NOT_CONFIGURED'
    assert readiness['execution_authority']=='none'


def test_readiness_probes_only_configured_own_mailbox_and_keeps_privacy():
    from scripts.verify_owned_imap_mailbox import readiness_report
    own,session=provider_factory()
    result=readiness_report(own,probe=False)
    assert result['status']=='CONFIGURED_UNPROVEN'
    assert result['live_probe_performed'] is False
    assert session==[]
    observed=readiness_report(own,probe=True)
    assert observed['status']=='READ_PROBE_SUCCESS'
    assert observed['live_probe_performed'] is True
    assert observed['inbox_rows_observed']==1
    assert observed['sent_rows_observed']==1
    assert observed['canonical_buyer_conversation_verified'] is False
    assert 'buyer@example.org' not in repr(observed)
    assert 'not_a_real_secret' not in repr(observed)


def test_readiness_probe_fails_closed_without_config(monkeypatch):
    from scripts.verify_owned_imap_mailbox import readiness_report
    for key in ('EMPIRE_FOUNDER_IMAP_HOST','EMPIRE_FOUNDER_IMAP_USER',
                'EMPIRE_FOUNDER_IMAP_PASSWORD'):
        monkeypatch.delenv(key,raising=False)
    result=readiness_report(OwnedIMAPMailboxProvider(),probe=True)
    assert result['status']=='CONFIGURATION_REQUIRED'
    assert result['live_probe_performed'] is False


def test_login_failure_closes_connection_and_returns_sanitized_reason():
    calls=[]
    class Rejecting:
        def login(self,user,password):
            raise ValueError('private-password should never appear in log')
        def logout(self):
            calls.append('LOGOUT')
    def factory(*args,**kwargs):return Rejecting()
    own=OwnedIMAPMailboxProvider(host='mail.empire-ai.co.uk',username='phil@mail.empire-ai.co.uk',
                                 password='private-password',client_factory=factory)
    with pytest.raises(MailboxReadUnavailable,match='OWN_IMAP_TLS_AUTH_UNAVAILABLE') as error:
        own.list_received(limit=1)
    assert calls==['LOGOUT']
    assert 'private-password' not in str(error.value)
