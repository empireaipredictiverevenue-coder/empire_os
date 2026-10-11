import pytest
from empire_os.reply_join_guard import assess_reply_joins


def event(kind='reply_received', message='m1', intent='i1'):
    return {'provider_message_id': message, 'intent_id': intent, 'event_type': kind}


def test_classification_updates_do_not_create_ambiguous_replies():
    result = assess_reply_joins([event()], [event(), event('reply_classified'), event('reply_classified'), event('reply_classified')])
    assert result['unique_event_link_count'] == 1
    assert result['results'][0]['status'] == 'UNIQUE_RECEIVED_EVENT'
    assert result['admission_authorized'] is False
    assert result['thread_contact_tenant_authenticated'] is False


def test_wrong_intent_and_duplicate_received_events_fail_closed():
    reply = [event()]
    assert assess_reply_joins(reply, [event(intent='i2')])['results'][0]['status'] == 'MISSING_RECEIVED_EVENT'
    assert assess_reply_joins(reply, [event(), event()])['results'][0]['status'] == 'AMBIGUOUS_RECEIVED_EVENTS'


def test_missing_type_and_invalid_rows_fail_closed():
    assert assess_reply_joins([event()], [{'provider_message_id': 'm1', 'intent_id': 'i1'}])['unique_event_link_count'] == 0
    with pytest.raises(ValueError):
        assess_reply_joins([None], [])
