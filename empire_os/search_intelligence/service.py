"""Loopback-only Search Intelligence read/preview service."""
from fastapi import FastAPI
from .api import router
from .nsh_owned_property import router as national_storm_hub_gsc_router


def build_search_intelligence_service() -> FastAPI:
    app = FastAPI(title="Empire Search Intelligence API", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router)
    app.include_router(national_storm_hub_gsc_router)

    @app.get("/health")
    def service_health() -> dict[str, object]:
        return {"ok": True, "service": "search-intelligence-api", "mode": "OBSERVE", "execution_allowed": False}

    return app


app = build_search_intelligence_service()
