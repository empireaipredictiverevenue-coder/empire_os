#!/usr/bin/env python3
"""Founder-owned IMAP readiness and optional bounded read-only connectivity.

Never prints credentials, host/user/address, message metadata or body content.
Does not send email or upgrade a provider reply to canonical buyer evidence.
"""
from __future__ import annotations
import argparse
import json
import time
from urllib import request, error
from typing import Any, Callable

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



SERVICE_BASE = 'http://127.0.0.1:8766'


class _NoRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _local_json(path: str, *, opener: Callable[..., Any] | None = None) -> dict:
    # Caller cannot supply a URL: no untrusted network destination or login.
    open_fn = opener or request.build_opener(_NoRedirects()).open
    req = request.Request(SERVICE_BASE + path, method='GET',
                          headers={'Accept': 'application/json'})
    with open_fn(req, timeout=5) as response:
        if response.status != 200:
            raise ValueError('unexpected_http_status')
        payload = json.loads(response.read(65536).decode('utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('invalid_service_payload')
    return payload


def service_readiness_report(*, probe: bool = False,
                             expected_provider: str = 'owned_imap',
                             opener: Callable[..., Any] | None = None,
                             startup_attempts: int = 1,
                             startup_sleep: Callable[[float], Any] = time.sleep) -> dict:
    """Check the *running* Founder API environment without reading credentials.

    --service-probe uses the existing read-only summary, bounded to one item
    per folder; it never prints person/message/secret fields.
    """
    if expected_provider not in ('owned_imap', 'google_workspace'):
        raise ValueError('unsupported_mailbox_readiness_provider')
    result = {
        'schema_version': (
            'empire.google_workspace_service_readiness.v1'
            if expected_provider == 'google_workspace'
            else 'empire.owned_imap_service_readiness.v1'
        ),
        'provider': expected_provider, 'mode': 'OBSERVE',
        'service_checked': True, 'configured': False,
        'read_only': True, 'live_probe_performed': False,
        'suppression_evidence_complete': False,
        'canonical_buyer_conversation_verified': False,
        'outbound_sent': False, 'execution_authority': 'none',
    }
    # A just-restarted Uvicorn process may be `active` before TCP is ready.
    # Retry ONLY connection/startup failures; never repeat IMAP reads or mask
    # real 404, credentials, policy, parsing, or provider mismatches.
    if type(startup_attempts) is not int or not 1 <= startup_attempts <= 12:
        raise ValueError('invalid_startup_attempt_count')
    status = None
    for attempt in range(startup_attempts):
        try:
            status = _local_json('/v1/founder-mailbox/readiness', opener=opener)
            break
        except error.HTTPError as exc:
            result['status'] = 'ROUTE_NOT_DEPLOYED' if exc.code == 404 else 'SERVICE_READINESS_UNAVAILABLE'
            result['http_status'] = int(exc.code)
            return result
        except (error.URLError, TimeoutError, OSError):
            if attempt + 1 < startup_attempts:
                startup_sleep(0.5)
                continue
            result['status'] = 'SERVICE_UNAVAILABLE'
            result['startup_checks_attempted'] = startup_attempts
            result['action'] = 'check_founder_api_service_status_without_restarting'
            return result
        except (ValueError, UnicodeError, TypeError, KeyError):
            result['status'] = 'SERVICE_RESPONSE_INVALID'
            return result
    if (status.get('provider') != expected_provider
        or status.get('execution_authority') != 'none'
        or status.get('canonical_identity_verified') is not False
        or status.get('suppression_evidence_complete') is not False):
        result['status'] = 'SERVICE_CONTRACT_UNVERIFIED'
        return result
    result['configured'] = status.get('configured') is True
    if not result['configured']:
        result['status'] = 'CONFIGURATION_REQUIRED'
        return result
    if not probe:
        result['status'] = 'CONFIGURED_UNPROVEN'
        return result
    result['live_probe_performed'] = True
    try:
        summary = _local_json('/v1/founder-mailbox/summary?limit=1', opener=opener)
    except error.HTTPError as exc:
        result['status'] = 'READ_PROBE_BLOCKED'
        result['http_status'] = int(exc.code)
        return result
    except (error.URLError, TimeoutError, OSError, ValueError, UnicodeError, TypeError, KeyError):
        result['status'] = 'READ_PROBE_BLOCKED'
        return result
    if (summary.get('provider') != expected_provider
        or summary.get('execution_authority') != 'none'
        or summary.get('canonical_buyer_conversation_verified') is not False
        or summary.get('suppression_evidence_complete') is not False):
        result['status'] = 'READ_PROBE_CONTRACT_UNVERIFIED'
        return result
    metrics = summary.get('summary')
    if not isinstance(metrics, dict):
        result['status'] = 'READ_PROBE_CONTRACT_UNVERIFIED'
        return result
    threads = metrics.get('all')
    if type(threads) is not int or not 0 <= threads <= 2:
        result['status'] = 'READ_PROBE_CONTRACT_UNVERIFIED'
        return result
    result['status'] = 'READ_PROBE_SUCCESS'
    result['threads_observed_in_sample'] = threads
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--probe', action='store_true',
                      help='Probe using credentials in the current process environment')
    mode.add_argument('--service', action='store_true',
                      help='Check the running loopback Founder API without credentials')
    mode.add_argument('--service-probe', action='store_true',
                      help='Read one item per folder through the running Founder API')
    args = parser.parse_args()
    output = (service_readiness_report(probe=args.service_probe,
                                       startup_attempts=12)
              if args.service or args.service_probe
              else readiness_report(OwnedIMAPMailboxProvider(), probe=args.probe))
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0 if output['status'] == 'READ_PROBE_SUCCESS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
