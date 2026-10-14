"""A one-to-one founder mail operator has no automatic send authority."""

import pytest

from scripts.operate_founder_one_to_one_gmail import policy_review, main
from empire_os.outbound_governor import POSTAL_ADDRESS

IID = '11111111-1111-4111-8111-111111111111'
EMAIL = 'one@example.org'


def review():
    return {
        'actual_revenue': False, 'channel': 'email', 'intent_id': IID,
        'recipient': EMAIL, 'status': 'approved',
        'subject': 'A relevant introduction',
        'body_text': 'Hello. To unsubscribe, reply opt out.\n\n' + POSTAL_ADDRESS,
        'expires_at': '2099-01-01T00:00:00Z',
    }


def context():
    return {
        'suppressed': False,
        'review_ready': True, 'outreach_ready': True,
        'bound_to_decision_maker': True,
        'contact_source': 'official_site', 'contact_confidence': 0.95,
        'company_score': 90, 'provider_ready': False,
        'exact_and_domain_suppression_cleared': True,
        'no_existing_canonical_contact_history': True,
    }


def test_no_send_review_stays_nonmutating():
    result = policy_review(review(), context(), recipient=EMAIL)
    assert result['mode'] == 'OBSERVE'
    assert result['mutation_authorized'] is False
    assert result['decision'] in ('READY_FOR_SEND_GATE', 'ESCALATE', 'HOLD')


def test_wrong_recipient_suppression_and_missing_review_are_held():
    with pytest.raises(ValueError, match='EXACT_RECIPIENT'):
        policy_review(review(), context(), recipient='other@example.org')
    other = context()
    other['suppressed'] = None
    with pytest.raises(ValueError, match='SUPPRESSION_UNVERIFIED'):
        policy_review(review(), other, recipient=EMAIL)
    other = context()
    other['bound_to_decision_maker'] = False
    with pytest.raises(ValueError, match='VERIFIED_PERSON_BOUND'):
        policy_review(review(), other, recipient=EMAIL)
    with pytest.raises(ValueError, match='TRANSPORT_NOT_VERIFIED'):
        policy_review(review(), context(), recipient=EMAIL, execution_requested=True)


def test_operator_requires_founder_release_before_any_database_access(monkeypatch, capsys):
    monkeypatch.delenv('EMPIRE_FOUNDER_MANUAL_GMAIL_RELEASE', raising=False)
    assert main(['--intent-id', IID, '--recipient', EMAIL,
                 '--send', '--confirm-approved-intent-id', IID]) == 2
    text = capsys.readouterr().out
    assert 'EXPLICIT_FOUNDER_SINGLE_INTENT_RELEASE_REQUIRED' in text
    assert '"message_sent": false' in text


def test_without_dedicated_sender_credentials_operator_fails_closed(monkeypatch, capsys):
    monkeypatch.delenv('EMPIRE_OUTBOUND_SENDER_DSN', raising=False)
    assert main(['--intent-id', IID, '--recipient', EMAIL]) == 2
    text = capsys.readouterr().out
    assert 'DEDICATED_CANONICAL_OUTBOUND_SENDER_UNAVAILABLE' in text
    assert '"message_sent": false' in text
