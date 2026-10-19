"""Unmounted, loopback-test-only HTTP adapter for Empire Analytics.

No production collector is created by this module. All routes are OFF
unless the factory receives an explicit local-test configuration AND a
test-only environment guard. Even then the adapter never writes events;
it runs the existing consent-gated simulation contract.

This is NOT an endpoint to mount on the public website or private
Founder Console. It is a hardened verification harness for the future
collector, preserving the existing Empire-owned gateway ownership.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
import json
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from empire_os.analytics.first_party_event_contract import (
    EventContractHeld, simulate_verified_batch,
)
from empire_os.owned_campaign_http import IntakeLimiter

PATH = "/v1/analytics/_simulation/events"
ORIGIN = "https://empire-ai.co.uk"
MAX_PAYLOAD_BYTES = 32 * 1024
TEST_GUARD_NAME = "EMPIRE_ANALYTICS_TEST_MODE"
TEST_GUARD_VALUE = "LOCAL_TEST_ONLY"

HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def build_dormant_event_ingress(
    *,
    allow_local_test_simulation: bool = False,
    approved_paths: Sequence[str] | None = None,
    resolve_server_consent: Callable[[str], bool] | None = None,
    resolve_server_channel: Callable[[str], str] | None = None,
    clock: Callable[[], datetime] | None = None,
    limiter: Any | None = None,
) -> APIRouter:
    """Return a route factory only. No existing app includes this router.

    Inproduction deployment without the exact LOCAL_TEST_ONLY guard
    cannot run the simulated intake, even if a caller accidentally
    includes this router. No ledger/writer/payment or cookie is present.
    """
    router = APIRouter(tags=["analytics-test-only"])
    ready = (
        allow_local_test_simulation is True
        and os.environ.get(TEST_GUARD_NAME) == TEST_GUARD_VALUE
        and approved_paths is not None
        and callable(resolve_server_consent)
        and callable(resolve_server_channel)
        and callable(clock)
    )
    request_limiter = limiter if limiter is not None else IntakeLimiter()

    def response(status: int, reason: str):
        return JSONResponse(
            {"status": reason, "accepted": False, "production_ingestion": False,
             "website_sessions_verified": False, "realised_revenue_verified": False},
            status_code=status, headers=HEADERS,
        )

    @router.post(PATH)
    async def check_event_envelope(request: Request):
        # Disabled is the default and runs before reading untrusted bytes.
        if not ready or os.environ.get(TEST_GUARD_NAME) != TEST_GUARD_VALUE:
            return response(503, "ANALYTICS_INGESTION_NOT_ACTIVATED")

        # No forwarded client-IP trust and no allowlist of arbitrary hosts.
        peer = request.client.host if request.client else ""
        if peer not in ("127.0.0.1", "::1"):
            return response(403, "ANALYTICS_TEST_LOCAL_PEER_REQUIRED")
        if (request.headers.get("origin") != ORIGIN
                or request.headers.get("sec-fetch-site") != "same-origin"
                or request.headers.get("cookie") is not None
                or request.headers.get("authorization") is not None):
            return response(403, "ANALYTICS_SIMULATION_ORIGIN_OR_CREDENTIALS_INVALID")
        if (request.headers.get("content-type", "").lower().strip()
                != "application/json"
                or request.headers.get("content-encoding") is not None):
            return response(415, "ANALYTICS_SIMULATION_JSON_REQUIRED")
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return response(400, "ANALYTICS_SIMULATION_LENGTH_INVALID")
            if not 0 <= size <= MAX_PAYLOAD_BYTES:
                return response(413, "ANALYTICS_SIMULATION_PAYLOAD_TOO_LARGE")
        if not request_limiter.allow(peer, "event"):
            return response(429, "ANALYTICS_SIMULATION_RATE_LIMITED")

        raw = bytearray()
        async for chunk in request.stream():
            if len(chunk) > MAX_PAYLOAD_BYTES - len(raw):
                return response(413, "ANALYTICS_SIMULATION_PAYLOAD_TOO_LARGE")
            raw.extend(chunk)
        try:
            payload = json.loads(raw)
            if type(payload) is not dict or set(payload) != {"events"}:
                raise EventContractHeld("ANALYTICS_SIMULATION_ENVELOPE_INVALID")
            summary = simulate_verified_batch(
                payload["events"],
                approved_paths=approved_paths,
                resolve_server_consent=resolve_server_consent,
                resolve_server_channel=resolve_server_channel,
                now=clock(),
            )
        except (ValueError, TypeError):
            # Never echo event IDs, internal resolver error, payload or PII.
            return response(422, "ANALYTICS_SIMULATION_EVENT_HELD")
        except Exception:
            return response(503, "ANALYTICS_SIMULATION_DEPENDENCY_UNAVAILABLE")
        return JSONResponse({
            "status": "OFFLINE_CONTRACT_SIMULATED_NOT_INGESTED",
            "accepted": False,
            "production_ingestion": False,
            "website_sessions_verified": False,
            "realised_revenue_verified": False,
            "simulation_only": True,
            "simulation": summary,
        }, status_code=200, headers=HEADERS)

    return router
