"""Provider-signed HTTP adapter for the candidate AI receptionist.

Separate FastAPI app, not mounted in any existing production service.
Never configure live Vonage answer URL until owner-controlled DID, privacy,
shared durable session/replay and end-to-end customer signoff are verified.
"""
from __future__ import annotations

import copy
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from empire_os.inbound_reception_call_flow import InboundReceptionCallEngine
from empire_os.inbound_signature_verification import (
    InvalidVoiceCallback, verify_vonage_voice_callback,
)


def create_inbound_reception_voice_app(
    *,
    engine: InboundReceptionCallEngine,
    signature_secret: str,
    api_key: str,
    application_id: str,
    enabled: bool = False,
) -> FastAPI:
    if not signature_secret or not api_key or not application_id:
        raise ValueError("signed_reception_credentials_required")

    app = FastAPI(
        title="Empire AI Receptionist — isolated signed call adapter",
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    recent: dict[str, tuple[str, list[dict]]] = {}
    lock = Lock()

    @app.middleware("http")
    async def privacy_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health")
    def health():
        return {
            "service": "empire-ai-receptionist-signed-candidate",
            "state": "dark-isolated-pilot" if enabled else "disabled",
            "voice_provider_connected": False,
            "real_did_routed": False,
            "booking_live": False,
            "customer_outbound_authorized": False,
            "shared_durable_call_storage_verified": False,
        }

    async def _handle(request: Request, stage: str) -> JSONResponse:
        if enabled is not True:
            raise HTTPException(status_code=404, detail="reception_adapter_disabled")
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(status_code=415, detail="json_webhook_required")
        try:
            raw = await request.body()
            callback = verify_vonage_voice_callback(
                request.headers.get("authorization", ""), raw,
                signature_secret=signature_secret,
                expected_api_key=api_key,
                expected_application_id=application_id,
            )
        except InvalidVoiceCallback as exc:
            raise HTTPException(status_code=401, detail="invalid_signed_voice_webhook") from exc
        import json
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(status_code=400, detail="invalid_voice_payload") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="invalid_voice_payload")
        # Single-process atomicity; no durable replay or call-state guarantees.
        # Held from production while these are not independently verified.
        with lock:
            prior = recent.get(callback.jwt_id)
            if prior is not None:
                if prior[0] != callback.payload_sha256:
                    raise HTTPException(status_code=409, detail="voice_callback_jti_reuse")
                return JSONResponse(content=copy.deepcopy(prior[1]))
            if len(recent) >= 5000:
                raise HTTPException(status_code=503, detail="voice_replay_capacity_held")
            try:
                result = (engine.answer(body) if stage == "answer"
                          else engine.reply(body))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="voice_call_route_held") from exc
            recent[callback.jwt_id] = (callback.payload_sha256, copy.deepcopy(result))
        return JSONResponse(content=result)

    @app.post("/v1/inbound-reception/vonage/answer")
    async def signed_answer(request: Request):
        return await _handle(request, "answer")

    @app.post("/v1/inbound-reception/vonage/input")
    async def signed_input(request: Request):
        return await _handle(request, "input")

    return app
