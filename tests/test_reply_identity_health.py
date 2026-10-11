import pytest
from empire_os.reply_identity_health import diagnose_reply_identity

def test_quarantined_records_are_not_accepted_and_repair_is_actionable():
    result = diagnose_reply_identity({'quarantine': {'records': [{'reasons': ['MISSING_STABLE_THREAD_ID', 'MISSING_CANONICAL_CONTACT_IDENTITY']}]}, 'entity_classification': {'candidate_count': 1, 'canonical_message_count': 0}})
    assert result['identity_ready'] is False
    assert result['write_authorized'] is False
    assert result['reason_counts']['MISSING_STABLE_THREAD_ID'] == 1
    assert len(result['repair_actions']) == 2

def test_complete_identity_contract():
    result = diagnose_reply_identity({'quarantine': {'records': []}, 'entity_classification': {'candidate_count': 1, 'canonical_message_count': 1}})
    assert result['identity_ready'] is True

@pytest.mark.parametrize('payload', [{}, {'quarantine': {'records': [{'reasons': 'bad'}]}, 'entity_classification': {'candidate_count': 1, 'canonical_message_count': 0}}, {'quarantine': {'records': [{}]}, 'entity_classification': {'candidate_count': 0, 'canonical_message_count': 0}}])
def test_invalid_contract_fails_closed(payload):
    with pytest.raises(ValueError):
        diagnose_reply_identity(payload)
