#!/usr/bin/env python3
"""Founder-owned IMAP readiness and optional bounded read-only connectivity.

Never prints credentials, host/user/address, message metadata or body content.
Does not send email or upgrade a provider reply to canonical buyer evidence.
"""
from __future__ import annotations
import argparse
import json

from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider, MailboxReadUnavailable


def readiness_report(provider: OwnedIMAPMailboxProvider, *, probe: bool = False) -> dict:
    status = provider.readiness()
    result = {
        'schema_version': 'empire.owned_imap_mailbox_readiness.v1',
        'provider': status['provider'],
        'mode': 'OBSERVE',
        'config_present': status['configured'],
        'tls_required': True,
        'read_only': True,
        'suppression_evidence_complete': False,
        'canonical_buyer_conversation_verified': False,
        'live_probe_performed': False,
        'outbound_sent': False,
        'execution_authority': 'none',
    }
    if not status['configured']:
        result['status'] = 'CONFIGURATION_REQUIRED'
        return result
    if not probe:
        result['status'] = 'CONFIGURED_UNPROVEN'
        return result
    result['live_probe_performed'] = True
    try:
        # Read at most one message per folder. The provider uses BODY.PEEK,
        # TLS certificate validation, IMAP UIDVALIDITY and read-only SELECT.
        received = provider.list_received(limit=1)
        sent = provider.list_sent(limit=1)
    except MailboxReadUnavailable as exc:
        result['status'] = 'READ_PROBE_BLOCKED'
        result['reason'] = str(exc)[:90]
        return result
    result['status'] = 'READ_PROBE_SUCCESS'
    result['inbox_rows_observed'] = len(received)
    result['sent_rows_observed'] = len(sent)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true',
                        help='Explicitly connect to your own IMAP server in read-only mode')
    args = parser.parse_args()
    output = readiness_report(OwnedIMAPMailboxProvider(), probe=args.probe)
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0 if output['status'] == 'READ_PROBE_SUCCESS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
