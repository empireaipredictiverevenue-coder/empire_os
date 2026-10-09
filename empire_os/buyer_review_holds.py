"""Strict, read-only founder due-diligence holds for buyer reviews.

A candidate held for missing independent legal or source evidence must not
become founder-review READY merely because a discovery score increases. This
policy does not create any ability to approve, send or modify buyers.
"""
from __future__ import annotations
import json
from pathlib import Path
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
        result[domain]={
            'reason_code':reason,
            'observed_on':str(item.get('observed_on') or ''),
            'resolution_condition':str(item.get('resolution_condition') or '')[:500],
            'review_required':True,
        }
    return result
