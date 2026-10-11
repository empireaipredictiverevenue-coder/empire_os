"""Strict, read-only founder due-diligence holds for buyer reviews.

A candidate held for missing independent legal or source evidence must not
become founder-review READY merely because a discovery score increases. This
policy does not create any ability to approve, send or modify buyers.
"""
from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache
import re
from urllib.parse import urlsplit
from typing import Any

MAX_BYTES = 32_768
_DOMAIN = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$')
_CODE = re.compile(r'^[A-Z][A-Z0-9_]{3,100}$')


class BuyerReviewHoldError(ValueError):
    pass


def load_review_holds(path: str | Path) -> dict[str, dict[str, Any]]:
    """A missing, modified or malformed review-hold inventory fails closed."""
    source=Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise BuyerReviewHoldError('buyer_review_hold_policy_missing_or_unsafe')
    try:
        payload=json.loads(source.read_text(encoding='utf-8'))
    except (OSError,ValueError,UnicodeError) as exc:
        raise BuyerReviewHoldError('buyer_review_hold_policy_unreadable') from exc
    if (not isinstance(payload,dict)
        or payload.get('schema_version')!='empire.buyer_network_manual_holds.v1'
        or not isinstance(payload.get('holds'),list)
        or len(payload['holds'])>100):
        raise BuyerReviewHoldError('buyer_review_hold_policy_invalid')
    result={}
    for item in payload['holds']:
        if not isinstance(item,dict):
            raise BuyerReviewHoldError('buyer_review_hold_entry_invalid')
        domain=item.get('domain')
        reason=item.get('reason_code')
        urls=item.get('evidence_urls')
        if (not isinstance(domain,str) or not _DOMAIN.fullmatch(domain)
            or domain!=domain.lower() or domain in result
            or item.get('state')!='HOLD'
            or item.get('review_required') is not True
            or not isinstance(reason,str) or not _CODE.fullmatch(reason)
            or not isinstance(urls,list) or not 1<=len(urls)<=10):
            raise BuyerReviewHoldError('buyer_review_hold_entry_invalid')
        for url in urls:
            if (not isinstance(url,str) or len(url)>500
                or urlsplit(url).scheme!='https'
                or (urlsplit(url).hostname or '').removeprefix('www.')!=domain):
                raise BuyerReviewHoldError('buyer_review_hold_source_invalid')
        do_not_pursue = item.get('do_not_pursue', False)
        blocked_recipients = item.get('blocked_recipients', [])
        if (type(do_not_pursue) is not bool
            or not isinstance(blocked_recipients,list)
            or len(blocked_recipients)>20
            or any(not isinstance(address,str)
                   or not re.fullmatch(r'[a-z0-9._+%-]+@'+re.escape(domain),address)
                   for address in blocked_recipients)
            or (blocked_recipients and not do_not_pursue)):
            raise BuyerReviewHoldError('buyer_review_hold_exclusion_invalid')
        result[domain]={
            'reason_code':reason,
            'observed_on':str(item.get('observed_on') or ''),
            'resolution_condition':str(item.get('resolution_condition') or '')[:500],
            'review_required':True,
            'do_not_pursue':do_not_pursue,
            'blocked_recipients':tuple(blocked_recipients),
        }
    return result


DEFAULT_HOLDS = Path(__file__).resolve().parents[1] / 'config/buyer_network_manual_review_holds.json'


@lru_cache(maxsize=12)
def _exclusions_at_version(path: str, mtime_ns: int, size: int) -> frozenset[str]:
    # Re-evaluate automatically after an atomic founder policy update.
    holds = load_review_holds(path)
    return frozenset(domain for domain, record in holds.items()
                     if record['do_not_pursue'] is True)


def do_not_pursue_domains(path: str | Path = DEFAULT_HOLDS) -> frozenset[str]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise BuyerReviewHoldError('buyer_review_hold_policy_missing_or_unsafe')
    stat = source.stat()
    return _exclusions_at_version(str(source), stat.st_mtime_ns, stat.st_size)


def is_do_not_pursue_domain(domain: str, *, path: str | Path = DEFAULT_HOLDS) -> bool:
    host = str(domain or '').strip().lower().rstrip('.').removeprefix('www.')
    return host in do_not_pursue_domains(path)
