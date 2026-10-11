#!/usr/bin/env python3
"""Bounded, read-only structural lineage probe. No PII or raw identifiers emitted."""
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
            cur.execute('SELECT intent_id FROM public.outbound_replies ORDER BY received_at DESC LIMIT 100')
            replies = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT id FROM public.outbound_intents WHERE id = ANY(%s)', (replies,))
            intents = Counter(r[0] for r in cur.fetchall())
            cur.execute('SELECT outbound_intent_id FROM public.empire_conversations WHERE outbound_intent_id = ANY(%s)', (replies,))
            conversations = Counter(r[0] for r in cur.fetchall())
            conn.rollback()
    counts = Counter()
    for intent in replies:
        i = intents[intent]
        c = conversations[intent]
        counts['intent_unique' if i == 1 else ('intent_missing' if i == 0 else 'intent_ambiguous')] += 1
        counts['conversation_unique' if c == 1 else ('conversation_missing' if c == 0 else 'conversation_ambiguous')] += 1
    print(json.dumps({'mode':'OBSERVE','reply_count':len(replies),'structural_counts':dict(sorted(counts.items())),'provider_thread_authenticated':False,'contact_authenticated':False,'tenant_authenticated':False,'admission_authorized':False,'outbound_authorized':False},sort_keys=True))


if __name__ == '__main__':
    main()
