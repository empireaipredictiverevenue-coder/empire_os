"""Strict browser contracts. Input never establishes canonical person identity."""
from datetime import datetime, timezone, timedelta
import re
from uuid import UUID

from empire_os.owned_campaign_preflight import REQUIRED_EVENTS, lookup_campaign, _landing

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+\Z")


def _strict(payload, required, optional=()):
    if not isinstance(payload, dict) or not set(required).issubset(payload) or set(payload) - set(required) - set(optional):
        raise ValueError('invalid fields')
    if any(not isinstance(v, str) for v in payload.values()):
        raise ValueError('string fields required')


def _binding(payload, marketing):
    c = lookup_campaign(marketing, payload['campaign_id'])
    if payload['asset_id'] != _landing(c).get('asset_id'):
        raise ValueError('campaign asset mismatch')
    return c


def validate_event(payload, marketing, *, now=None):
    _strict(payload, ('event_id', 'event_type', 'campaign_id', 'asset_id', 'source', 'channel', 'occurred_at'), ('session_id',))
    _binding(payload, marketing)
    if payload['event_type'] not in REQUIRED_EVENTS or payload['source'] != 'owned_site' or payload['channel'] != 'organic':
        raise ValueError('unsupported event')
    result = dict(payload)
    for key in ('event_id', 'session_id'):
        if key in result:
            value = UUID(result[key])
            if value.version != 4:
                raise ValueError('random UUID required')
            result[key] = str(value)
    stamp = datetime.fromisoformat(payload['occurred_at'].replace('Z', '+00:00'))
    now = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp > now + timedelta(minutes=5) or stamp < now - timedelta(days=7):
        raise ValueError('event time outside collection window')
    result['occurred_at'] = stamp.astimezone(timezone.utc).isoformat()
    return result


def validate_enquiry(payload, marketing):
    _strict(payload, ('campaign_id', 'asset_id', 'reply_email', 'research_question'), ('company', 'role'))
    _binding(payload, marketing)
    result = {k: v.strip() for k, v in payload.items()}
    result['reply_email'] = result['reply_email'].lower()
    if len(result['reply_email']) > 254 or not EMAIL.fullmatch(result['reply_email']):
        raise ValueError('invalid email')
    if not 10 <= len(result['research_question']) <= 4000:
        raise ValueError('question length')
    for key, maximum in (('company', 200), ('role', 100)):
        if len(result.get(key, '')) > maximum:
            raise ValueError('optional field length')
        if not result.get(key):
            result.pop(key, None)
    if any(any(ord(ch) < 32 and ch not in '\n\t' for ch in v) for v in result.values()):
        raise ValueError('control character')
    return result


def accept(kind, payload, marketing, repository):
    normalized = validate_enquiry(payload, marketing) if kind == 'enquiry' else validate_event(payload, marketing)
    receipt = repository.enquiry(normalized) if kind == 'enquiry' else repository.event(normalized)
    return {'accepted': True, 'receipt_id': receipt, 'campaign_id': normalized['campaign_id']}
