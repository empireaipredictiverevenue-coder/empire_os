"""Bounded request handling shared by the existing gateway's two intake routes."""
import hashlib
import hmac
import json
import secrets
import threading
import time

from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from empire_os.data_backends.owned_campaign_repository import OwnedCampaignRepository
from empire_os.owned_campaign_intake import accept
from empire_os.owned_campaign_release import load_release


class IntakeLimiter:
    """Bounded ephemeral abuse state, never a business or identity store.

    Does not trust forwarding headers. A shared proxy bucket is conservative;
    deployment must verify ingress limits before using forwarded client identity.
    """
    def __init__(self):
        self.secret = secrets.token_bytes(32)
        self.buckets = {}
        self.lock = threading.Lock()

    def allow(self, peer, kind, now=None):
        now = time.monotonic() if now is None else now
        key = (hmac.new(self.secret, peer.encode(), hashlib.sha256).digest(), kind)
        with self.lock:
            self.buckets = {k: v for k, v in self.buckets.items() if now - v[0] < 60}
            if key not in self.buckets and len(self.buckets) >= 4096:
                return False
            stamp, count = self.buckets.get(key, (now, 0))
            self.buckets[key] = (stamp, count + 1)
            return count < (5 if kind == 'enquiry' else 60)


LIMITER = IntakeLimiter()


async def handle_intake(request, kind, *, origin='https://empire-ai.co.uk'):
    headers = {'Cache-Control': 'no-store'}
    def error(code, status):
        return JSONResponse({'accepted': False, 'error': code}, status_code=status, headers=headers)
    if kind not in ('event', 'enquiry', 'industry_event'):
        return error('unsupported_intake_kind', 404)
    if request.headers.get('origin') != origin or request.headers.get('sec-fetch-site', 'same-origin') not in ('same-origin', 'none'):
        return error('same_origin_required', 403)
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
        return error('json_required', 415)
    peer = request.client.host if request.client else 'unknown'
    if not LIMITER.allow(peer, kind):
        return error('rate_limited', 429)
    try:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 12000:
                return error('request_too_large', 413)
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        return error('invalid_json', 400)
    marketing = await run_in_threadpool(load_release)
    if marketing is None:
        return error('campaign_intake_unavailable', 503)
    if kind == 'industry_event':
        from empire_os.owned_campaign_industry_extension import (
            load_industry_release, validate_industry_event, validate_industry_referrer,
        )
        release = await run_in_threadpool(
            lambda: load_industry_release(research_release=marketing)
        )
        if release is None:
            return error('industry_campaign_unreleased', 503)
    try:
        repository = OwnedCampaignRepository.from_environment()
        if kind == 'industry_event':
            normalized = validate_industry_event(payload, release)
            validate_industry_referrer(request.headers.get('referer'), normalized, release)
            receipt = await run_in_threadpool(repository.event, normalized)
            result = {'accepted': True, 'receipt_id': receipt,
                      'campaign_id': normalized['campaign_id']}
        else:
            result = await run_in_threadpool(accept, kind, payload, marketing, repository)
    except ValueError:
        return error('invalid_request', 422)
    except Exception:
        # Never disclose driver text, SQL, credentials or enquiry fields.
        return error('campaign_intake_unavailable', 503)
    return JSONResponse(result, status_code=202, headers=headers)
