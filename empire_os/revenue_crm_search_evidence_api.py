"""Stored search evidence route for the existing authenticated CRM router.

Install with its request-scoped require_repository callback. Never mount with
a global repository or a tenant/header-derived callback.
"""
from typing import Callable
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from empire_os.revenue_crm_search_growth import build_crm_search_growth_brief
from empire_os.search_intelligence.backlinks import BacklinkObservation
from empire_os.search_intelligence.ai_visibility import AiCitationObservation

SEARCH_EVIDENCE_SQL = (
    "SELECT tenant_id,payload FROM public.empire_crm_search_evidence(%s,%s,%s,%s,%s)"
)


def _refs(value):
    if (not isinstance(value, list) or not value
            or any(not isinstance(ref, str) or not ref.strip() for ref in value)):
        raise ValueError('invalid stored provenance')
    return tuple(value)


def _stored_brief(payload, *, prospect_id, site_id, query, engine, limit):
    if not isinstance(payload, dict):
        raise ValueError('invalid stored envelope')
    status = payload.get('status')
    if status == 'NOT_CONNECTED':
        if set(payload) != {'status'}:
            raise ValueError('unexpected unbound evidence')
        return {'status': status, 'brief': None}
    if status not in ('CONNECTED_NO_OBSERVATIONS', 'CONNECTED_OBSERVATIONS'):
        raise ValueError('invalid connection state')
    for field, expected in (('prospect_id', prospect_id), ('site_id', site_id),
                            ('query', query), ('engine', engine)):
        if payload.get(field) != expected:
            raise ValueError('stored scope mismatch')
    UUID(payload['entity_id'])
    base = urlsplit(payload['base_url'])
    if (base.scheme not in ('https', 'http') or not base.hostname
            or base.username is not None or base.password is not None):
        raise ValueError('invalid bound site URL')
    _refs([payload.get('binding_evidence_ref')])
    backlinks, citations = [], []
    for kind, result in (('backlinks', backlinks), ('citations', citations)):
        rows = payload.get(kind)
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('invalid stored observations')
        if type(payload.get(kind + '_truncated')) is not bool:
            raise ValueError('invalid truncation state')
        for row in rows:
            if not isinstance(row, dict) or row.get('site_id') != site_id:
                raise ValueError('foreign site observation')
            UUID(row['id'])
            refs = _refs(row.get('provenance'))
            if kind == 'backlinks':
                observation = BacklinkObservation(
                    source_url=row['source_url'], target_url=row['target_url'],
                    observed_at=row['observed_at'], anchor_text=row.get('anchor_text'),
                    rel=row.get('rel'), source=row['source'], provenance=refs,
                )
            else:
                if row.get('query') != query or row.get('engine') != engine:
                    raise ValueError('foreign query observation')
                observation = AiCitationObservation(
                    query=query, engine=engine, observed_at=row['observed_at'],
                    cited_url=row['cited_url'], source_url=row.get('source_url'),
                    citation_position=row.get('citation_position'),
                    mention_text=row.get('mention_text'), provenance=refs,
                )
            observation.validate()
            result.append(observation)
    has_rows = bool(backlinks or citations)
    if has_rows != (status == 'CONNECTED_OBSERVATIONS'):
        raise ValueError('inconsistent observation state')
    brief = build_crm_search_growth_brief(
        prospect_id=prospect_id, domain=base.hostname, query=query, engine=engine,
        backlinks=tuple(backlinks), citations=tuple(citations),
    )
    return {
        'status': status, 'site_id': site_id,
        'binding_evidence_ref': payload['binding_evidence_ref'],
        'backlinks_truncated': payload['backlinks_truncated'],
        'citations_truncated': payload['citations_truncated'],
        'brief': brief.as_dict(),
    }


def install_crm_search_evidence_route(
    router: APIRouter, *, require_authenticated_repository: Callable,
) -> None:
    @router.get('/prospects/{prospect_id}/search-growth')
    def stored_search_growth(
        request: Request, prospect_id: UUID, site_id: UUID,
        query: str = Query(min_length=1, max_length=2000),
        engine: str = Query(min_length=1, max_length=100),
        limit: int = Query(default=100, ge=1, le=100),
    ):
        if not query.strip() or not engine.strip():
            raise HTTPException(status_code=422, detail='invalid_search_selector')
        try:
            repo = require_authenticated_repository(request)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'authenticated_crm_read_unavailable') from None
        try:
            if not isinstance(repo, PostgresRevenueCrmRepository):
                raise ValueError('authenticated repository required')
            tenant = str(UUID(repo.tenant_id))
            # Reuse the CRM transport's login, read-only, timeout and tenant checks.
            rows = repo._fetch_all(SEARCH_EVIDENCE_SQL,
                                   (str(prospect_id), str(site_id), query, engine, limit))
            if len(rows) != 1 or str(rows[0].get('tenant_id')) != tenant:
                raise ValueError('invalid scoped result')
            result = _stored_brief(rows[0]['payload'], prospect_id=str(prospect_id),
                                   site_id=str(site_id), query=query, engine=engine, limit=limit)
        except Exception:
            raise HTTPException(503, 'authenticated_crm_search_evidence_unavailable') from None
        return dict(result, mode='OBSERVE', read_only=True, execution_authority='none',
                    source='canonical_crm_search_reader', crm_mutation=False,
                    publishing_execution=False, outreach_execution=False)
