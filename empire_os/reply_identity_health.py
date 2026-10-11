"""Read-only, privacy-preserving reply identity readiness diagnosis."""
from __future__ import annotations
from collections import Counter
from typing import Any

REPAIR_MAP = {
    'MISSING_STABLE_MESSAGE_ID': 'Capture provider message ID at inbound ingestion.',
    'MISSING_STABLE_THREAD_ID': 'Bind reply to verified provider thread or outbound intent before admission.',
    'MISSING_CANONICAL_CONTACT_IDENTITY': 'Resolve sender to a canonical contact using verified identity evidence.',
}


def diagnose_reply_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError('conversation snapshot must be an object')
    quarantine = snapshot.get('quarantine')
    classification = snapshot.get('entity_classification')
    if not isinstance(quarantine, dict) or not isinstance(classification, dict):
        raise ValueError('missing quarantine or classification contract')
    records = quarantine.get('records')
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError('invalid quarantine records')
    counts = Counter()
    for row in records:
        reasons = row.get('reasons')
        if not isinstance(reasons, list) or any(not isinstance(x, str) for x in reasons):
            raise ValueError('invalid quarantine reason contract')
        counts.update(set(reasons))
    admitted = classification.get('canonical_message_count')
    if type(admitted) is not int or admitted < 0:
        raise ValueError('invalid canonical message count')
    candidate_count = classification.get('candidate_count')
    if type(candidate_count) is not int or candidate_count < admitted:
        raise ValueError('invalid candidate count')
    if len(records) > candidate_count or admitted + len(records) > candidate_count:
        raise ValueError('inconsistent quarantine counts')
    return {
        'mode': 'OBSERVE', 'execution_authority': 'none',
        'candidate_count': candidate_count, 'canonical_message_count': admitted,
        'quarantined_count': len(records),
        'unresolved_candidate_count': candidate_count - admitted - len(records),
        'identity_ready': bool(admitted) and not records and admitted == candidate_count,
        'reason_counts': dict(sorted(counts.items())),
        'repair_actions': [REPAIR_MAP.get(reason, 'Inspect source contract for this quarantine reason.')
                           for reason in sorted(counts)],
        'write_authorized': False,
    }
