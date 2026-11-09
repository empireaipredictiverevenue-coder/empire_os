"""Mount stored evidence after the unchanged original CRM startup."""
from fastapi import APIRouter, HTTPException
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from .revenue_crm_search_evidence_api import install_crm_search_evidence_route

PATH = "/v1/revenue-crm/prospects/{prospect_id}/search-growth"

def attach_search_evidence(app, resolver):
    if getattr(app.state, "crm_search_evidence_mounted", False) or any(
            getattr(r, "path", None) == PATH for r in app.routes):
        raise RuntimeError("CRM search route already mounted")
    def require_repository(request):
        try:
            access = resolver(request)
        except Exception:
            raise HTTPException(503, "authenticated_crm_read_unavailable") from None
        if access is None:
            raise HTTPException(401, "authenticated_crm_scope_required")
        if (not isinstance(access, AuthenticatedRevenueCrmRead)
                or not isinstance(access.repository, PostgresRevenueCrmRepository)
                or access.tenant_id != access.repository.tenant_id):
            raise HTTPException(503, "authenticated_crm_read_unavailable")
        return access.repository
    router = APIRouter(prefix="/v1/revenue-crm")
    install_crm_search_evidence_route(router, require_authenticated_repository=require_repository)
    app.include_router(router)
    app.state.crm_search_evidence_mounted = True
