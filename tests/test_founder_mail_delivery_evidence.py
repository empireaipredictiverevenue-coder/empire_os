"""Historic internal delivery evidence must not become outbound approval."""
import json
from copy import deepcopy

import pytest

from empire_os.founder_mail_delivery_evidence import load_historical_mail_evidence


def fixture():
    return {
        'schema_version': 'empire.founder_mail.delivery_observation.v1',
        'source': 'FOUNDER_CONNECTED_GMAIL_READ_ONLY',
        'observed_on': '2026-10-14',
        'historical_test_date': '2026-10-13',
        'sender_test': {
            'gmail_message_id': '1a13690028a25d18',
            'observed_from': 'phil@mail.empire-ai.co.uk',
            'dkim_signing_domain': 'empire-ai.co.uk',
            'header_from_domain': 'mail.empire-ai.co.uk',
            'spf_pass': True, 'dkim_pass': True, 'dmarc_pass': True,
            'recipient_is_founder_controlled': True,
        },
        'reply_base_test': {
            'gmail_message_id': '1a1360f9e950523c',
            'original_recipient': 'reply@mail.empire-ai.co.uk',
            'visible_forward_to_founder': True,
            'provider_inbound_observed': True,
        },
        'reply_alias_test': {
            'gmail_message_id': '1a136752af4ca4b0',
            'visible_forward_to_founder': True,
            'provider_inbound_observed': True,
            'intent_alias_correlated': True,
            'synthetic_test_only': True,
        },
        'prospect_send_authorized': False,
        'new_email_sent_by_this_check': False,
        'direct_workspace_inbox_auth_verified': False,
        'canonical_business_reply_verified': False,
        'credentials_included': False,
    }


def store(tmp_path, value):
    path = tmp_path / 'delivery.json'
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


def test_valid_historical_evidence_is_observed_not_authority(tmp_path):
    result = load_historical_mail_evidence(store(tmp_path, fixture()))
    assert result['founder_sender_reached_controlled_inbox'] is True
    assert result['sender_spf_dkim_dmarc_passed'] is True
    assert result['reply_base_forwarded'] is True
    assert result['reply_alias_forwarded'] is True
    assert result['direct_workspace_inbox_verified'] is False
    assert result['canonical_business_reply_verified'] is False
    assert result['prospect_send_authorized'] is False
    assert result['new_email_sent'] is False
    assert 'gmail_message_id' not in str(result)


def test_fabricated_evidence_or_clearance_fails_closed(tmp_path):
    for mutate in (
        lambda x: x.update(prospect_send_authorized=True),
        lambda x: x['sender_test'].update(dmarc_pass=False),
        lambda x: x['reply_alias_test'].update(synthetic_test_only=False),
        lambda x: x['reply_base_test'].update(visible_forward_to_founder=False),
        lambda x: x.update(direct_workspace_inbox_auth_verified=True),
        lambda x: x['sender_test'].update(observed_from='other@example.org'),
    ):
        val = deepcopy(fixture())
        mutate(val)
        with pytest.raises(ValueError):
            load_historical_mail_evidence(store(tmp_path, val))


def test_world_readable_evidence_is_rejected(tmp_path):
    path = store(tmp_path, fixture())
    path.chmod(0o644)
    with pytest.raises(ValueError, match='INSECURE'):
        load_historical_mail_evidence(path)
