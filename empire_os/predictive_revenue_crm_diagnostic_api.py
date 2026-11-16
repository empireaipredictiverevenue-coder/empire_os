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
from empire_os.predictive_revenue_customer_history import (
    CustomerHistoryInputError, MAX_UPLOAD_BYTES, preview_customer_history_csv,
)

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

    @router.post('/customer-history/forecast-preview')
    async def customer_history_forecast_preview(request: Request):
        """Ephemeral 30-day upload preview; never persists or registers data."""
        if (set(request.query_params) - {'horizon_days'}
                or len(request.query_params.getlist('horizon_days')) > 1):
            raise HTTPException(422, 'customer_history_request_invalid')
        raw_horizon = request.query_params.get('horizon_days', '30')
        try:
            horizon = int(raw_horizon)
        except (TypeError, ValueError):
            raise HTTPException(422, 'customer_history_request_invalid') from None
        if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'text/csv':
            raise HTTPException(415, 'customer_history_csv_required')
        length = request.headers.get('content-length')
        if length is not None:
            try:
                if not 1 <= int(length) <= MAX_UPLOAD_BYTES:
                    raise ValueError
            except (TypeError, ValueError):
                raise HTTPException(413, 'customer_history_upload_too_large_or_empty') from None
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
            # Verify the existing DB session_user -> tenant binding before
            # processing the transient upload. This performs only a bounded
            # read; user-supplied tenant fields are never accepted.
            access.repository.prospects(limit=1)
            bounded = bytearray()
            async for chunk in request.stream():
                if len(bounded) + len(chunk) > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'customer_history_upload_too_large_or_empty')
                bounded.extend(chunk)
            return preview_customer_history_csv(
                bytes(bounded), tenant_id=access.tenant_id,
                as_of=datetime.now(timezone.utc), horizon_days=horizon,
            )
        except CustomerHistoryInputError as exc:
            raise HTTPException(422, str(exc)) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'authenticated_diagnostic_source_unavailable') from None

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
