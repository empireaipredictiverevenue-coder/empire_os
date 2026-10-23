"""Catch genuine-source header candidates outside original nine Gmail threads."""
from datetime import datetime, timezone

import pytest

from empire_os.founder_acquisition_standalone_inbound import discover, STATE
from empire_os.workspace_solar_reply_tracking import EvidenceHeld
from tests.test_founder_acquisition_autopilot import (
    CLOCK, fixture_ledger, fixture_results, sent_message, inbound_message,
)


class MetadataOnlyMail:
    def __init__(self, refs, message_by_id, *, next_token=None):
        self.refs = refs
        self.records = message_by_id
        self.next_token = next_token
        self.actions = []
    def users(self):
        return self
    def messages(self):
        return self
    def list(self, **kw):
        self.action = ('list', kw)
        self.actions.append(self.action)
        return self
    def get(self, **kw):
        self.action = ('get', kw)
        self.actions.append(self.action)
        return self
    def execute(self):
        kind, args = self.action
        if kind == 'list':
            val = {'messages': self.refs}
            if self.next_token:
                val['nextPageToken'] = self.next_token
            return val
        return self.records[args['id']]


def _setup(tmp_path):
    ledger = fixture_ledger(tmp_path)
    threads = fixture_results(ledger)
    company, email, original = ledger['anchors'][1]
    mid, tid = 'bb99999999999999', 'cc99999999999999'
    incoming = inbound_message(tid, email, ident=mid)
    incoming['payload']['headers'][-1]['value'] = '<legitimate@empire-ai.co.uk>'
    return ledger, threads, (company, email, original, mid, tid, incoming)


def test_no_external_messages_safe_zero_result(tmp_path):
    ledger, threads, values = _setup(tmp_path)
    api = MetadataOnlyMail([], {})
    x = discover(api, ledger['anchors'], threads, now=CLOCK)
    assert x['status'] == STATE
    assert x['standalone_inbound_candidate_count'] == 0
    assert x['new_standalone_inbound_candidates'] == 0
    assert x['outbound_sent'] is False
    assert x['automatic_reply_authorized'] is False
    assert any('from:alloovium.com' in str(a) for a in api.actions)
    assert any(a[1].get('maxResults') == 50 for a in api.actions)


def test_new_standalone_original_sender_is_review_only(tmp_path):
    ledger, threads, (company, email, original, mid, tid, incoming) = _setup(tmp_path)
    api = MetadataOnlyMail([{'id':mid,'threadId':tid}], {mid:incoming})
    x = discover(api,ledger['anchors'],threads,now=CLOCK)
    assert x['standalone_inbound_candidate_count'] == 1
    assert x['new_standalone_inbound_candidates'] == 1
    v = x['standalone_inbound_header_candidates'][0]
    assert v['company'] == company
    assert v['gmail_message_id'] == mid
    assert v['rfc_parent_relation'] == 'DIRECT_PARENT_MATCH'
    assert v['sender_correspondence'] == 'EXACT_ORIGINAL_RECIPIENT'
    assert v['buyer_intent_verified'] is False
    assert email not in str(v)  # Never persist sender identity
    assert 'body' not in str(v).lower()
    assert api.actions[-1][1]['format'] == 'metadata'
    assert api.actions[-1][1]['metadataHeaders'] == ['From','To','Message-ID','In-Reply-To','References']


def test_repeat_does_not_count_same_candidate_twice(tmp_path):
    ledger, threads, (_, _, _, mid, tid, incoming) = _setup(tmp_path)
    api = MetadataOnlyMail([{'id':mid,'threadId':tid}], {mid:incoming})
    one=discover(api,ledger['anchors'],threads,now=CLOCK)
    two=discover(api,ledger['anchors'],threads,now=CLOCK,
                 previous={'standalone_inbound_header_candidates':one['standalone_inbound_header_candidates']})
    assert two['standalone_inbound_candidate_count']==1
    assert two['new_standalone_inbound_candidates']==0


def test_previous_candidate_disappearing_holds(tmp_path):
    ledger, threads, (_, _, _, mid, tid, incoming) = _setup(tmp_path)
    api=MetadataOnlyMail([{'id':mid,'threadId':tid}],{mid:incoming})
    one=discover(api,ledger['anchors'],threads,now=CLOCK)
    with pytest.raises(EvidenceHeld,match='STANDALONE_PRIOR_CANDIDATE_DISAPPEARED'):
        discover(MetadataOnlyMail([],{}),ledger['anchors'],threads,now=CLOCK,
                 previous={'standalone_inbound_header_candidates':one['standalone_inbound_header_candidates']})


def test_incomplete_gmail_search_holds(tmp_path):
    ledger, threads, values = _setup(tmp_path)
    api = MetadataOnlyMail([],{},next_token='next-page')
    with pytest.raises(EvidenceHeld,match='STANDALONE_GMAIL_SEARCH_INCOMPLETE'):
        discover(api, ledger['anchors'],threads,now=CLOCK)


def test_do_not_double_count_original_thread_inbound(tmp_path):
    ledger, threads, (company,email,original,mid,tid,incoming) = _setup(tmp_path)
    incoming['threadId']=original
    api=MetadataOnlyMail([{'id':mid,'threadId':original}],{mid:incoming})
    x=discover(api,ledger['anchors'],threads,now=CLOCK)
    assert x['standalone_inbound_candidate_count']==0
    assert not [a for a in api.actions if a[0]=='get']


@pytest.mark.parametrize('reason', ['wrong_sender','sent','old_date','wrong_to'])
def test_untrusted_header_variants_are_not_founder_replies(tmp_path, reason):
    ledger,threads,(company,email,original,mid,tid,incoming)=_setup(tmp_path)
    if reason=='wrong_sender':
        incoming['payload']['headers'][0]['value']='Person <other@example.org>'
    elif reason=='sent':
        incoming['labelIds']=['SENT']
    elif reason=='old_date':
        incoming['internalDate']='1792749000000'
    else:
        incoming['payload']['headers'][1]['value']='someone@example.org'
    api=MetadataOnlyMail([{'id':mid,'threadId':tid}],{mid:incoming})
    x=discover(api,ledger['anchors'],threads,now=CLOCK)
    assert x['standalone_inbound_candidate_count']==0
    assert x['outbound_sent'] is False
