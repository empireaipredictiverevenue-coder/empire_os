#!/usr/bin/env python3
"""Read-only, bounded proof of reply/event identity cardinality (no raw IDs)."""
from __future__ import annotations
import json
import os
import psycopg
from empire_os.reply_join_guard import assess_reply_joins


def main():
    dsn = os.environ.get('EMPIREDB_DSN')
    if not dsn:
        raise SystemExit('EMPIREDB_DSN not configured; no probe performed')
    with psycopg.connect(dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute('BEGIN READ ONLY')
            cur.execute('SELECT provider_message_id, intent_id FROM public.outbound_replies ORDER BY received_at DESC LIMIT 100')
            replies = [{'provider_message_id': r[0], 'intent_id': r[1]} for r in cur.fetchall()]
            cur.execute('SELECT provider_message_id, intent_id, event_type FROM public.outbound_events WHERE provider_message_id IS NOT NULL ORDER BY created_at DESC LIMIT 2000')
            events = [{'provider_message_id': r[0], 'intent_id': r[1], 'event_type': r[2]} for r in cur.fetchall()]
            conn.rollback()
    result = assess_reply_joins(replies, events)
    counts = {}
    for row in result['results']:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    print(json.dumps({'mode': 'OBSERVE', 'reply_count': result['reply_count'], 'event_rows_examined': len(events), 'join_status_counts': counts, 'thread_contact_tenant_authenticated': False, 'admission_authorized': False, 'outbound_authorized': False}, sort_keys=True))


if __name__ == '__main__':
    main()
