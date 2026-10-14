"""Specific-recipient preflight checks domain and historical suppressions."""
import pytest

from empire_os.founder_one_to_one_suppression import (
    read_one_to_one_preflight, OneToOnePreflightUnavailable,
)
from scripts.operate_founder_one_to_one_gmail import policy_review
from tests.test_founder_one_to_one_operator import review, context

IID = '11111111-1111-4111-8111-111111111111'


class FakeCursor:
    def __init__(self, suppressed=0, historical=0):
        self.values = iter([(suppressed,), (historical,)])
        self.executed = []
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def execute(self, query, params=None):
        self.executed.append((query, params))
    def fetchone(self):
        return next(self.values)


class FakeConnection:
    def __init__(self, suppressed=0, historical=0):
        self.cursor_inst = FakeCursor(suppressed, historical)
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def cursor(self):
        return self.cursor_inst


def read(suppressed=0, historical=0):
    con = FakeConnection(suppressed, historical)
    result = read_one_to_one_preflight('test-read-dsn',
        recipient='one@example.org', intent_id=IID,
        connect_factory=lambda *a, **k: con)
    return result, con


def test_role_bound_read_only_check_covers_email_and_domain():
    result, con = read()
    assert result['exact_and_domain_suppression_cleared'] is True
    assert result['no_existing_canonical_contact_history'] is True
    assert result['other_mailboxes_checked'] is False
    assert result['send_authorized'] is False
    assert con.cursor_inst.executed[0][0] == 'SET TRANSACTION READ ONLY'
    assert con.cursor_inst.executed[1][0] == 'SET LOCAL ROLE empire_outbound_sender'
    assert con.cursor_inst.executed[3][1] == (
        'one@example.org', 'example.org', '@example.org'
    )
    assert con.cursor_inst.executed[4][1] == ('one@example.org', IID)
    assert con.cursor_inst.executed[-1][0] == 'ROLLBACK'


def test_domain_suppression_and_prior_contact_are_hard_holds():
    result, _ = read(suppressed=1, historical=0)
    ctx = context()
    ctx['exact_and_domain_suppression_cleared'] = result['exact_and_domain_suppression_cleared']
    with pytest.raises(ValueError, match='DOMAIN_SUPPRESSION'):
        policy_review(review(), ctx, recipient='one@example.org')
    result, _ = read(suppressed=0, historical=2)
    ctx = context()
    ctx['no_existing_canonical_contact_history'] = result['no_existing_canonical_contact_history']
    with pytest.raises(ValueError, match='EXISTING_CANONICAL_CONTACT'):
        policy_review(review(), ctx, recipient='one@example.org')


def test_malformed_data_and_driver_error_cannot_clear_contact():
    with pytest.raises(OneToOnePreflightUnavailable):
        read_one_to_one_preflight('', recipient='one@example.org', intent_id=IID)
    with pytest.raises(OneToOnePreflightUnavailable):
        read_one_to_one_preflight('test', recipient='not-an-email', intent_id=IID)
    with pytest.raises(OneToOnePreflightUnavailable):
        read_one_to_one_preflight('test', recipient='one@example.org', intent_id=IID,
                                  connect_factory=lambda *a, **k: FakeConnection(True, 0))
    with pytest.raises(OneToOnePreflightUnavailable) as exc:
        read_one_to_one_preflight('test', recipient='one@example.org', intent_id=IID,
                                  connect_factory=lambda *a, **k: (_ for _ in ()).throw(RuntimeError('private-connection')))
    assert 'private-connection' not in str(exc.value)
