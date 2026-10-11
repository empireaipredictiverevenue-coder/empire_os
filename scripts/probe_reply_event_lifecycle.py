#!/usr/bin/env python3
"""Read-only aggregate lifecycle diagnostic; prints no IDs, contacts or bodies."""
from __future__ import annotations
import json
import os
from collections import Counter
import psycopg


def main():
    dsn = os.getenv('EMPIREDB_DSN')
    if not dsn:
        raise SystemExit('EMPIREDB_DSN unavailable')
    with psycopg.connect(dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute('BEGIN READ ONLY')
            cur.execute('SELECT provider_message_id, intent_id FROM public.outbound_replies ORDER BY received_at DESC LIMIT 100')
            replies = cur.fetchall()
            cur.execute('SELECT provider_message_id, intent_id, event_type FROM public.outbound_events WHERE provider_message_id IS NOT NULL ORDER BY created_at DESC LIMIT 2000')
            events = cur.fetchall()
            conn.rollback()
    index = {}
    for message, intent, event_type in events:
        if message is not None and intent is not None:
            index.setdefault((str(message), str(intent)), []).append(str(event_type or 'UNSPECIFIED'))
    patterns = Counter()
    for message, intent in replies:
        types = index.get((str(message), str(intent)), [])
        patterns[json.dumps({'event_rows': len(types), 'event_types': dict(sorted(Counter(types).items()))}, sort_keys=True)] += 1
    print(json.dumps({'mode': 'OBSERVE', 'reply_count': len(replies), 'lifecycle_patterns': [{'pattern': json.loads(k), 'reply_count': v} for k,v in sorted(patterns.items())], 'admission_authorized': False, 'outbound_authorized': False}, sort_keys=True))


if __name__ == '__main__':
    main()
