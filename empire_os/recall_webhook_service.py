"""Dedicated loopback Recall webhook service for Digital Avatar SHADOW mode."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from empire_os.recall_verified_spool import FileRecallVerifiedSpool
from empire_os.recall_webhook_api import (
    create_recall_lifecycle_webhook_router,
    create_recall_webhook_router,
)


SPOOL_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_VERIFIED_SPOOL",
        "/srv/empire_os/runtime/digital_avatar/recall_ingress",
    )
)
MAX_PAYLOAD_BYTES = int(
    os.getenv("EMPIRE_RECALL_MAX_PAYLOAD_BYTES", "512000")
)
SPOOL = FileRecallVerifiedSpool(
    SPOOL_ROOT,
    max_payload_bytes=MAX_PAYLOAD_BYTES,
)
LIFECYCLE_SPOOL_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_LIFECYCLE_SPOOL",
        os.getenv(
            "EMPIRE_RECALL_STATUS_SPOOL",
            "/srv/empire_os/runtime/digital_avatar/recall_lifecycle_ingress",
        ),
    )
)
LIFECYCLE_SPOOL = FileRecallVerifiedSpool(
    LIFECYCLE_SPOOL_ROOT,
    max_payload_bytes=MAX_PAYLOAD_BYTES,
)
# Compatibility aliases for older status-lane tests/config.
STATUS_SPOOL_ROOT = LIFECYCLE_SPOOL_ROOT
STATUS_SPOOL = LIFECYCLE_SPOOL


def _secret() -> str:
    return os.getenv("RECALL_WORKSPACE_VERIFICATION_SECRET", "").strip()


def _sink(envelope):
    return SPOOL.enqueue(envelope)


def _status_secret() -> str:
    return (
        os.getenv("RECALL_SVIX_WEBHOOK_SECRET", "").strip()
        or _secret()
    )


def _status_sink(envelope):
    return STATUS_SPOOL.enqueue(envelope)


def _lifecycle_sink(envelope):
    # STATUS_SPOOL remains a compatibility injection seam for tests/ops.
    return STATUS_SPOOL.enqueue(envelope)


app = FastAPI(
    title="Empire Recall Realtime Ingress",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(
    create_recall_webhook_router(
        secret_provider=_secret,
        verified_envelope_sink=_sink,
    )
)
app.include_router(
    create_recall_lifecycle_webhook_router(
        secret_provider=_status_secret,
        verified_envelope_sink=_lifecycle_sink,
    )
)


@app.get("/health")
def health():
    configured = bool(_secret())
    status_configured = bool(_status_secret())
    return JSONResponse(
        {
            "ok": configured and status_configured,
            "mode": "OBSERVE",
            "provider": "recall",
            "workspace_verification_configured": configured,
            "lifecycle_verification_configured": status_configured,
            "status_verification_configured": status_configured,
            "verified_spool": str(SPOOL_ROOT),
            "lifecycle_spool": str(LIFECYCLE_SPOOL_ROOT),
            "status_spool": str(STATUS_SPOOL_ROOT),
            "meeting_join_execution": False,
            "speech_execution": False,
            "commercial_execution": False,
            "execution_authority": "none",
        },
        status_code=200 if (configured and status_configured) else 503,
    )
