#!/usr/bin/env python3
"""Read-only metadata coverage report; never emit raw message content or identifiers."""
import json
import os
from collections import Counter
import psycopg

THREAD_KEYS = {'thread_id','provider_thread_id','gmail_thread_id','in_reply_to','references','conversation_id','external_conversation_id'}
AUTH_KEYS = {'provider','source','mailbox','tenant_id','contact_id','person_id','lead_id','authenticated','signature_verified'}


def main():
    dsn = os.getenv('EMPIREDB_DSN')
    if not dsn:
        raise SystemExit('EMPIREDB_DSN unavailable')
    with psycopg.connect(dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute('BEGIN READ ONLY')
            cur.execute('SELECT metadata FROM public.outbound_replies ORDER BY received_at DESC LIMIT 100')
            rows = cur.fetchall()
            conn.rollback()
    key_counts = Counter()
    types = Counter()
    for (meta,) in rows:
        if not isinstance(meta, dict):
            types['non_object'] += 1
            continue
        types['object'] += 1
        for key, val in meta.items():
            name = str(key).casefold()
            if name in THREAD_KEYS | AUTH_KEYS and val not in (None, '', [], {}):
                key_counts[name] += 1
    print(json.dumps({'mode':'OBSERVE','reply_count':len(rows),'metadata_types':dict(types),'recognized_evidence_key_coverage':dict(sorted(key_counts.items())),'values_exposed':False,'provider_thread_authenticated':False,'contact_authenticated':False,'tenant_authenticated':False,'admission_authorized':False,'outbound_authorized':False,'execution_authority':'none'},sort_keys=True))


if __name__ == '__main__':
    main()
