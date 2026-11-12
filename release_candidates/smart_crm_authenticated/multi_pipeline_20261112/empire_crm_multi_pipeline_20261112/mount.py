"""Additive Pipedrive-style board behind the existing authenticated CRM resolver.

Static login shell has no customer data. JSON rows always require the original
signed founder tenant reader, dedicated login, DB read guard and tenant binding.
"""
from datetime import datetime,timezone
from pathlib import Path
from typing import Callable
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse,Response
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository,RevenueCrmTransportError,
)
from .revenue_crm_multi_pipeline import (
    PipelineProjectionError,build_multi_pipeline_board,
)

API="/v1/revenue-crm/pipelines"
PATHS=(API+"/board",API+"/view",API+"/board.js")
STATIC=Path(__file__).resolve().parent

def attach_multi_pipeline_board(app, resolver:Callable)->None:
    if getattr(app.state,"empire_multi_pipeline_board_mounted",False):
        raise RuntimeError("pipeline board already mounted")
    # FastAPI uses lazy _IncludedRouter wrappers in the deployed version.
    # Count actual router additions; rehearsal probes exact effective GET paths.
    prior_count=len(app.router.routes)
    if not callable(resolver):
        raise RuntimeError("canonical tenant resolver required")

    def require_repo(request:Request)->PostgresRevenueCrmRepository:
        try:
            access=resolver(request)
        except Exception:
            raise HTTPException(503,"authenticated_crm_read_unavailable") from None
        if access is None:
            raise HTTPException(401,"authenticated_crm_scope_required")
        if (not isinstance(access,AuthenticatedRevenueCrmRead)
                or not isinstance(access.repository,PostgresRevenueCrmRepository)
                or access.tenant_id!=access.repository.tenant_id):
            raise HTTPException(503,"authenticated_crm_read_unavailable")
        return access.repository

    router=APIRouter(prefix=API,tags=["revenue-crm"])

    @router.get("/board")
    def board(request:Request,limit:int=Query(default=200,ge=1,le=500),
              pipeline:str|None=Query(default=None,max_length=64)):
        repo=require_repo(request)
        try:
            prospects=repo.prospects(limit=limit)
            buyers=repo.buyers(limit=limit)
        except RevenueCrmTransportError:
            raise HTTPException(503,"authenticated_crm_read_unavailable") from None
        try:
            return build_multi_pipeline_board(
                prospects,buyers,authenticated_tenant_id=repo.tenant_id,
                now=datetime.now(timezone.utc),pipeline=pipeline,
            )
        except PipelineProjectionError:
            raise HTTPException(503,"crm_pipeline_source_invalid") from None

    @router.get("/view",response_class=HTMLResponse)
    def view():
        return HTMLResponse(
            (STATIC/"revenue_crm_multi_pipeline_board.html").read_text("utf-8"),
            headers={
                "Cache-Control":"no-store",
                "X-Content-Type-Options":"nosniff",
                "Content-Security-Policy":(
                    "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
                    "connect-src 'self'; base-uri 'none'; object-src 'none'; "
                    "form-action 'none'; frame-ancestors 'none'"
                ),
            },
        )

    @router.get("/board.js")
    def script():
        return Response(
            (STATIC/"revenue_crm_multi_pipeline_board.js").read_bytes(),
            media_type="text/javascript",
            headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"},
        )

    app.include_router(router)
    app.state.empire_multi_pipeline_board_mounted=True
    if len(app.router.routes)!=prior_count+1:
        raise RuntimeError("CRM pipeline expected one additive router wrapper")
