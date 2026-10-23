"""Read-only status of existing EmpireOS commercial product owners."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
import json

MEDIA_PATH = Path('runtime/media_os/latest.json')
CONTRACTOR_PATH = Path('runtime/contractor_demand/founder_research_latest.json')


def _source(root: Path, relative: Path, now: datetime) -> dict[str, Any] | None:
    path = root / relative
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 250000:
            return None
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            return None
        stamp = datetime.fromisoformat(str(payload['generated_at']).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return None
        age = now - stamp.astimezone(timezone.utc)
        if not timedelta(0) <= age <= timedelta(hours=24):
            return None
        return payload
    except (OSError, ValueError, TypeError, KeyError):
        return None


def review_media(data: Mapping[str, Any] | None) -> dict[str, Any]:
    result = {'status':'HELD_MEDIAOS_RECEIPT_UNVERIFIED',
              'source_count':None, 'enquiry_proven':False,
              'causal_attribution_proven':False,'public_publish_authorized':False}
    if (not isinstance(data, Mapping)
        or data.get('schema_version') != 'empire.media_os.runtime.v1'
        or data.get('mode') != 'OBSERVE'
        or data.get('execution_authority') != 'none'
        or data.get('actual_revenue') is not False
        or data.get('public_publish_authorized') is not False
        or data.get('database_write_performed') is not False
        or data.get('external_action_performed') is not False
        or type(data.get('observed_source_count')) is not int):
        return result
    n = data['observed_source_count']
    if not 0 <= n <= 100:
        return result
    result.update(status='MEDIAOS_INTERNAL_RESEARCH_ONLY',source_count=n)
    return result


def review_contractor(data: Mapping[str, Any] | None) -> dict[str, Any]:
    result = {'status':'HELD_CONTRACTOR_SOURCE_UNVERIFIED',
              'research_candidate_count':None,
              'job_receipt_verified':False,'signed_installer_verified':False,
              'commercial_revenue_verified':False}
    if (not isinstance(data, Mapping)
        or data.get('schema_version') != 'empire.contractor_autonomous_research.v1'
        or data.get('status') != 'RESEARCH_READY'
        or data.get('mode') != 'OBSERVE'
        or data.get('execution_authority') != 'none'
        or data.get('provider_registry_connected') is not False
        or data.get('public_api_exposure_enabled') is not False
        or data.get('live_outbound') is not False
        or data.get('bids_submitted') != 0
        or data.get('crm_writes') != 0
        or data.get('realised_revenue') != 0):
        return result
    bids=data.get('bid_readiness')
    if not isinstance(bids,Mapping) or type(bids.get('candidate_count')) is not int:
        return result
    n=bids['candidate_count']
    if not 0 <= n <= 1000:
        return result
    result.update(status='CONTRACTOR_TENDER_RESEARCH_ONLY',research_candidate_count=n)
    return result


def observe_extended_products(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    current=now or datetime.now(timezone.utc)
    return {
        'media_os':review_media(_source(root, MEDIA_PATH, current)),
        'contractor_research':review_contractor(_source(root, CONTRACTOR_PATH, current)),
        'agency':{'status':'HELD_TENANT_GRANT_AND_SIGNING_PROOF_REQUIRED',
                  'tenant_authority_verified':False,
                  'customer_enquiry_verified':False},
        'job_matching':{'status':'HELD_CANONICAL_JOB_READER_AND_NAMED_CONSENT_REQUIRED',
                        'live_job_intake_verified':False,
                        'named_installer_consent_verified':False,
                        'paid_matching_verified':False},
        'execution_authority':'none',
        'crm_write_performed':False,
        'outreach_sent':False,
        'payment_action':False,
    }
