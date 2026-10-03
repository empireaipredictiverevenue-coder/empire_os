"""Dedicated loopback-only vertical intelligence service."""

from fastapi import FastAPI

from empire_os.founder_vertical_intelligence_api import (
    create_founder_vertical_intelligence_router,
)


def build_founder_vertical_intelligence_service():
    app = FastAPI(
        title="Empire Founder Vertical Intelligence API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "service":
                "founder-vertical-intelligence-api",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "persistence_allowed": False,
            "outbound_allowed": False,
            "payment_allowed": False,
            "revenue_recognition_allowed": False,
        }

    app.include_router(
        create_founder_vertical_intelligence_router()
    )

    return app


app = build_founder_vertical_intelligence_service()
