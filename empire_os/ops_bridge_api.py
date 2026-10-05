"""Public ciphertext-only result surface for the Empire Ops GitHub bridge."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

RESULTS = Path("/srv/empire_os/runtime/ops_bridge/results")
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def create_ops_bridge_router() -> APIRouter:
    router = APIRouter(prefix="/v1/ops-bridge", tags=["ops-bridge"])

    @router.get("/health")
    def health():
        return {
            "ok": True,
            "transport": "github-pull",
            "results": "encrypted_only",
            "general_shell": False,
        }

    @router.get("/result/{request_id}")
    def result(request_id: str):
        rid = str(request_id or "").strip().lower()
        if not REQUEST_ID_RE.fullmatch(rid):
            return JSONResponse({"error": "invalid_request_id"}, status_code=400)
        path = RESULTS / f"{rid}.pem"
        if not path.is_file():
            return JSONResponse(
                {"error": "result_not_ready"},
                status_code=404,
                headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
            )
        return PlainTextResponse(
            path.read_text(encoding="utf-8"),
            media_type="application/pkcs7-mime",
            headers={
                "Cache-Control": "no-store",
                "X-Robots-Tag": "noindex, nofollow",
            },
        )

    return router
