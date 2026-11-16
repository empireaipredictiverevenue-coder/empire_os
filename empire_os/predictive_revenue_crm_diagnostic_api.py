"""Original authenticated CRM -> original enterprise diagnostic, no new service.

The caller supplies the CRM host's existing verified tenant resolver. This
adapter never accepts a tenant, credentials, records or approval from HTTP.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response

from empire_os.enterprise_report_http_guard import guarded_enterprise_http_response
from empire_os.predictive_revenue_crm_diagnostic_adapter import (
    CrmDiagnosticEvidenceUnavailable, build_authenticated_crm_diagnostic_report,
)
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

PREFIX = '/v1/revenue-crm/predictive-diagnostic'
STATIC = Path(__file__).resolve().parent / 'predictive_revenue_crm_diagnostic_ui'


def create_authenticated_predictive_diagnostic_router(
    resolve_authenticated_read: Callable, *, repo_root: Path = Path('/srv/empire_os'),
) -> APIRouter:
    """A request-scoped report using exactly the existing CRM read authority."""
    if not callable(resolve_authenticated_read):
        raise ValueError('existing authenticated CRM resolver required')
    router = APIRouter(prefix=PREFIX, tags=['revenue-crm'])

    def report_response(request: Request, limit: int, format: str):
        if set(request.query_params) - {'limit'}:
            raise HTTPException(422, 'unsupported_diagnostic_query')
        try:
            access = resolve_authenticated_read(request)
        except Exception:
            raise HTTPException(503, 'authenticated_diagnostic_source_unavailable') from None
        if access is None:
            raise HTTPException(401, 'authenticated_crm_scope_required')
        if (type(access) is not AuthenticatedRevenueCrmRead
                or type(access.repository) is not PostgresRevenueCrmRepository
                or access.tenant_id != access.repository.tenant_id):
            raise HTTPException(503, 'authenticated_diagnostic_source_unavailable')
        try:
            # The source adapter independently rechecks repository identity;
            # its Postgres transport verifies session_user tenant binding and
            # SET LOCAL ROLE on a read-only transaction before source SELECT.
            # Resolve the HTTP principal once, not twice with different scopes.
            packet = build_authenticated_crm_diagnostic_report(
                repo_root,
                request=request, resolve_authenticated_crm=lambda _: access,
                as_of=datetime.now(timezone.utc), limit=limit,
            )
            # Existing release guard remains authoritative. Authenticated
            # bounded rows do not establish complete financial outcomes.
            return guarded_enterprise_http_response(packet, format=format)
        except (CrmDiagnosticEvidenceUnavailable, ValueError, TypeError, KeyError, OSError):
            raise HTTPException(503, 'authenticated_diagnostic_source_unavailable') from None

    @router.get('')
    def diagnostic(request: Request, limit: int = Query(default=500, ge=1, le=500)):
        return report_response(request, limit, 'json')

    @router.get('/preview')
    def preview(request: Request, limit: int = Query(default=500, ge=1, le=500)):
        return report_response(request, limit, 'html')

    @router.get('/markdown')
    def markdown(request: Request, limit: int = Query(default=500, ge=1, le=500)):
        return report_response(request, limit, 'markdown')

    @router.get('/app', response_class=HTMLResponse)
    def app_page():
        return HTMLResponse(
            (STATIC / 'index.html').read_text('utf-8'),
            headers={
                'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
                'Content-Security-Policy': (
                    "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
                    "connect-src 'self'; base-uri 'none'; object-src 'none'; "
                    "form-action 'none'; frame-ancestors 'none'"
                ),
            },
        )

    @router.get('/app.js')
    def app_script():
        return Response(
            (STATIC / 'app.js').read_bytes(),
            media_type='text/javascript',
            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
        )

    return router
