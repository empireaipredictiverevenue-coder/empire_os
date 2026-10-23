import pytest
from empire_os.outbound_governor_executor import execute_governor_decision, OutboundGovernorExecutionError


class Rpc:
    def __init__(self, fingerprint):
        self.fingerprint=fingerprint
        self.calls=[]
    def __call__(self, name, params):
        self.calls.append((name,params))
        if name=='claim_outbound_send':
            return dict(decision='authorized_send',intent_id='00000000-0000-0000-0000-000000000001',channel='email',recipient='buyer@example.com',subject='Hello',body_text='Hello. Reply opt out. 68 Wentbridge Road, Bolton, BL1 2QR, UK',body_html=None,actual_revenue=False,metadata={'copy_draft_id':self.fingerprint} if self.fingerprint else {})
        return {'status':'sent'}


class Transport:
    provider='mock'
    def send(self,payload):
        return 'provider-message-1'


def execute(rpc):
    from unittest.mock import patch
    with patch('empire_os.outbound_provider.require_no_commercial_hold', return_value=None):
        return execute_governor_decision(dict(decision='AUTO_SEND_ELIGIBLE',intent_id='00000000-0000-0000-0000-000000000001',mode='GUARDED_EXECUTE',mutation_authorized=True), sender_rpc=rpc,actor='test',sender='Phil - Founder - Empire AI <founder@empire-ai.co.uk>',reply_to='reply@mail.empire-ai.co.uk',email_transport=Transport())


def test_claimed_fingerprint_retained_in_existing_delivery_record():
    token='copy-sha256:'+'a'*64
    rpc=Rpc(token);execute(rpc)
    assert rpc.calls[-1][0]=='record_outbound_delivery'
    assert rpc.calls[-1][1]['p_payload']['copy_draft_id']==token
    assert rpc.calls[-1][1]['p_provider_message_id']=='provider-message-1'


def test_absent_fingerprint_preserves_legacy_record():
    rpc=Rpc(None);execute(rpc)
    assert 'copy_draft_id' not in rpc.calls[-1][1]['p_payload']


def test_bad_claim_fingerprint_blocks_before_send():
    rpc=Rpc('untrusted')
    with pytest.raises(OutboundGovernorExecutionError,match='fingerprint'):
        execute(rpc)
    assert not any(name=='record_outbound_delivery' for name,_ in rpc.calls)
