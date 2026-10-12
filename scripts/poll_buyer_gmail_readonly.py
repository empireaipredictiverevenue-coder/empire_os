#!/usr/bin/env python3
"""Bounded Gmail metadata reader for four known buyer threads; never sends mail."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from email.utils import parseaddr
from empire_os.buyer_mail_semantics import recognize_message_payload
from empire_os.buyer_thread_discovery import discover
from scripts.import_connected_gmail_buyer_metadata import THREADS, ROOT, INDEX, SCHEMA
from scripts.reconcile_buyer_email_relationships import atomic_private_write

READ_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
TOKEN = ROOT / 'runtime/secrets/buyer-gmail-readonly-token.json'


def collect(service, *, now=None, known_domains=None, additional_threads=None, additional_names=None):
    known_domains = known_domains or {}
    threads = []
    names = {'lead-smart':'Lead Smart', 'leadbank':'LeadBank',
             'validated':'Validated / Home Services Lead Group', 'connexis':'Connexis'}
    monitored=dict(THREADS)
    for tid,key in (additional_threads or {}).items():
        if tid not in monitored and isinstance(tid,str) and isinstance(key,str):
            monitored[tid]=key
    if len(monitored)>24:
        raise ValueError("GMAIL_MONITORING_SCOPE_TOO_LARGE")
    for tid, key in monitored.items():
        # Full payload read ONLY in memory. Persist event codes and message IDs,
        # never the raw email text, sender secrets or personal caller details.
        response = service.users().threads().get(
            userId='me', id=tid, format='full',
        ).execute()
        records = response.get('messages')
        if not isinstance(records, list) or not 1 <= len(records) <= 80:
            raise ValueError('INCOMPLETE_GMAIL_THREAD')
        messages = []
        for item in records:
            headers = {h['name'].lower(): h['value'] for h in item.get('payload',{}).get('headers',[])
                       if h.get('name','').lower() in ('from','to','cc','subject')}
            millis = int(item['internalDate'])
            date = datetime.fromtimestamp(millis/1000,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
            labels=item.get('labelIds',[])
            sender = parseaddr(headers.get('from',''))[1].strip().lower()
            expected_domains = set(known_domains.get(key, ()))
            buyer_sender = (
                sender.count('@') == 1
                and sender.split('@',1)[1] in expected_domains
                and 'SENT' not in labels and 'DRAFT' not in labels
                and 'SPAM' not in labels and 'TRASH' not in labels
            )
            founder_sender = sender == 'flavag83@gmail.com' and 'SENT' in labels
            events = (recognize_message_payload(
                item.get('payload') or {}, outbound=founder_sender,
            ) if buyer_sender or founder_sender else [])
            row={'id':item['id'], 'date':date,
                'from':headers.get('from',''), 'to':[a.strip() for a in headers.get('to','').split(',') if a.strip()],
                'cc':[a.strip() for a in headers.get('cc','').split(',') if a.strip()],
                'subject':headers.get('subject',''), 'labels':labels,
                'has_attachment':False, 'attachment_names':[]}
            if events:
                row['recognized_codes']=events
            messages.append(row)
        partner=(additional_names or {}).get(tid) or names.get(key,key)
        threads.append({'partner':partner, 'thread_id':tid, 'message_count':len(messages),
                        'truncated':False, 'messages':messages})
    return {'schema_version':SCHEMA,'source':'empire_gmail_api_readonly',
            'collected_at':(now or datetime.now(timezone.utc)).isoformat(),
            'original_message_bodies':'remain_in_gmail_not_copied_to_server',
            'scope':'four_existing_warm_partner_threads','threads':threads}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        if not TOKEN.is_file() or TOKEN.is_symlink() or TOKEN.stat().st_mode & 0o077:
            raise ValueError('READONLY_OAUTH_TOKEN_NOT_CONFIGURED')
        creds=Credentials.from_authorized_user_file(str(TOKEN),[READ_SCOPE])
        granted = set(creds.scopes or [])
        if READ_SCOPE not in granted or any('gmail.send' in scope or 'gmail.modify' in scope for scope in granted):
            raise ValueError('READONLY_OAUTH_SCOPE_UNSAFE')
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if not creds.valid or READ_SCOPE not in set(creds.scopes or []):
                raise ValueError('READONLY_OAUTH_REFRESH_FAILED')
            atomic_private_write(TOKEN, json.loads(creds.to_json()))
        if not creds.valid:
            raise ValueError('READONLY_OAUTH_NOT_VALID')
        from scripts.import_connected_gmail_buyer_metadata import _private, SOURCE, refreshed_summary
        original = _private(ROOT/SOURCE, 2500000)
        known_domains = {}
        for row in original.get("threads", []):
            if (row.get("gmail_thread_id") in THREADS
                    or row.get("automatic_discovery_link") is True):
                key = row["entity_key"]
                known_domains.setdefault(key,set()).update(row["identity_domains"])
        extra={
            row["gmail_thread_id"]:row["entity_key"]
            for row in original.get("threads",[])
            if row.get("automatic_discovery_link") is True
        }
        extra_names={
            row["gmail_thread_id"]:row["company"]
            for row in original.get("threads",[])
            if row.get("automatic_discovery_link") is True
        }
        service=build('gmail','v1',credentials=creds,cache_discovery=False)
        result=collect(service,known_domains=known_domains,
                       additional_threads=extra,additional_names=extra_names)
        prior_index={}
        if (ROOT/INDEX).is_file():
            try:
                prior_index=_private(ROOT/INDEX,900000)
            except (OSError, ValueError):
                prior_index={}
        prior_discovery=prior_index.get("discovery") or {}
        result["discovery"]=discover(
            service,original,cursor=prior_discovery.get("next_cursor",0),
        )
        # Validate the entire candidate against the existing buyer evidence
        # contract before replacing the private index. Never write partial data.
        refreshed_summary(original, result)
        if args.write:
            atomic_private_write(ROOT/INDEX,result)
        print(json.dumps({'status':'PASS','written':args.write,'threads':len(result['threads']),
                          'messages':sum(x['message_count'] for x in result['threads']),
                          'recognized_claim_events':sum(len(m.get('recognized_codes',[])) for x in result['threads'] for m in x['messages']),
                          'new_thread_candidates_checked':result['discovery']['checked_thread_count'],
                          'new_known_buyer_threads_found':result['discovery']['known_buyer_threads'],
                          'new_unknown_identity_review_found':result['discovery']['unlinked_review_count'],
                          'new_thread_discovery_incomplete':result['discovery']['incomplete_scan'],
                          'outbound_authorized':False}))
        return 0
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED','reason_code':str(exc) if isinstance(exc,ValueError) else type(exc).__name__,
                          'outbound_authorized':False}))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
