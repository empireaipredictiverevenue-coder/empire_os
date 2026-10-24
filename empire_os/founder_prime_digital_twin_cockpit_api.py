"""Private Founder read-model for original PRIME Digital Twin rehearsal.

This route never starts inference, accepts real conversation text, sends mail,
or writes state. Security/ingress ownership still governs deployment.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from empire_os.prime_digital_twin_cockpit import build_prime_digital_twin_cockpit


def create_founder_prime_digital_twin_cockpit_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-dashboard",
        tags=["founder-dashboard"],
    )

    @router.get("/prime-digital-twin")
    def original_prime_twin(
        scenario: str = Query(default="pricing_resolution", min_length=2, max_length=56),
        depth: int = Query(default=2, ge=0, le=2),
    ) -> dict:
        # The domain function also enforces the allowlist; never accept prompt
        # strings, URLs, provider credentials, identities, tenant IDs, or JSON.
        from fastapi import HTTPException
        try:
            return build_prime_digital_twin_cockpit(
                scenario_id=scenario, fractal_depth=depth,
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="unavailable_fictional_scenario"
            ) from None

    return router
