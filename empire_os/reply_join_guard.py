"""Fail-closed read-only reply-to-event cardinality checks."""
from __future__ import annotations
from collections import Counter
from typing import Any


def assess_reply_joins(replies: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Count only received events; classification events are lifecycle updates.

    A unique received event proves event cardinality only, never the
    authenticity of the provider, thread, contact or tenant.
    """
    if not isinstance(replies, list) or not isinstance(events, list):
        raise ValueError('reply and event inputs must be lists')
    if any(not isinstance(row, dict) for row in replies + events):
        raise ValueError('reply and event rows must be objects')
    received = Counter()
    for event in events:
        message = str(event.get('provider_message_id') or '').strip()
        intent = str(event.get('intent_id') or '').strip()
        if message and intent and event.get('event_type') == 'reply_received':
            received[(message, intent)] += 1
    results = []
    for reply in replies:
        message = str(reply.get('provider_message_id') or '').strip()
        intent = str(reply.get('intent_id') or '').strip()
        count = received[(message, intent)] if message and intent else 0
        status = 'UNIQUE_RECEIVED_EVENT' if count == 1 else ('AMBIGUOUS_RECEIVED_EVENTS' if count > 1 else 'MISSING_RECEIVED_EVENT')
        results.append({'status': status, 'received_event_match_count': count})
    return {
        'mode': 'OBSERVE', 'execution_authority': 'none',
        'reply_count': len(replies),
        'unique_event_link_count': sum(x['status'] == 'UNIQUE_RECEIVED_EVENT' for x in results),
        'results': results,
        'thread_contact_tenant_authenticated': False,
        'admission_authorized': False, 'outbound_authorized': False,
    }
