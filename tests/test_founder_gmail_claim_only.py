"""The owned Gmail adapter has no standalone payload entrypoint."""
import pytest

from empire_os.outbound_email_transport import GovernedGmailEmailTransport
from empire_os.outbound_provider import OutboundProviderError


def test_regular_transport_payload_is_refused():
    instance = GovernedGmailEmailTransport(token_file="fixture")
    with pytest.raises(OutboundProviderError, match="GMAIL_REQUIRES_GOVERNED_DATABASE_CLAIM"):
        instance.send({})


def test_mismatched_sender_does_not_reach_external_api():
    instance = GovernedGmailEmailTransport(token_file="fixture")
    with pytest.raises(OutboundProviderError, match="GMAIL_FOUNDER_SENDER_CONTRACT_UNVERIFIED"):
        instance.send_claim({}, sender="other@example.org", reply_to="reply@mail.empire-ai.co.uk")


def test_existing_governor_routes_authorised_claim_to_gmail(monkeypatch):
    from unittest.mock import Mock
    from empire_os.outbound_governor_executor import execute_governor_decision
    from tests.test_outbound_governor_executor import Rpc, guarded
    import empire_os.outbound_email_transport as transport_module
    gmail = Mock(return_value={'provider':'gmail','provider_message_id':'fake-gmail-id'})
    monkeypatch.setattr(transport_module, 'send_with_gmail_api', gmail)
    rpc = Rpc()
    result = execute_governor_decision(
        guarded('AUTO_SEND_ELIGIBLE'), sender_rpc=rpc, actor='test-founder',
        sender='Phil <phil@mail.empire-ai.co.uk>',
        reply_to='reply@mail.empire-ai.co.uk',
        email_transport=GovernedGmailEmailTransport(
            token_file='/srv/empire_os/runtime/secrets/google-workspace-internal-token.json'
        ),
    )
    assert result['provider_message_id'] == 'fake-gmail-id'
    assert [name for name,_ in rpc.calls] == ['claim_outbound_send','record_outbound_delivery']
    assert gmail.call_count == 1
