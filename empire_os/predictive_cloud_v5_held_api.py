"""Original V5 public API prototypes, unmounted and disabled pending owner approval."""
from fastapi import APIRouter, HTTPException, WebSocket
from empire_os.predictive_cloud_v5_whitelabel_shadow import readiness

def create_v5_held_api_router() -> APIRouter:
    router=APIRouter(tags=['predictive-cloud-v5-held'])
    @router.get('/v5/status')
    def status():
        return readiness()
    @router.post('/v5/router/dispatch')
    def dispatch():
        raise HTTPException(status_code=403,detail='v5_dispatch_owner_approval_required')
    @router.post('/v5/admin/tenants')
    def provision():
        raise HTTPException(status_code=403,detail='v5_canonical_tenant_owner_approval_required')
    @router.websocket('/v5/metrics/stream')
    async def metrics(ws:WebSocket):
        await ws.close(code=1008)
    return router
