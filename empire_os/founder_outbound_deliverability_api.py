"""Read-only Founder API for outbound deliverability health."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from empire_os.outbound_deliverability_provider import ResendMetricsProvider
from empire_os.outbound_deliverability_service import build_rolling_health
from empire_os.outbound_founder_alerts import build_founder_alert
from empire_os.outbound_postgres_repository import (
    configured_deliverability_repository_from_env,
)
from empire_os.outbound_state_replay import replay_health_state


def create_founder_outbound_deliverability_router(
    provider=None,
    repository=None,
) -> APIRouter:
    source = provider or ResendMetricsProvider()
    evidence_repository = (
        repository
        if repository is not None
        else configured_deliverability_repository_from_env()
    )
    router = APIRouter(
        prefix="/v1/founder-outbound-deliverability",
        tags=["founder-outbound-deliverability"],
    )

    @router.get("")
    def snapshot():
        try:
            health = build_rolling_health(source)
            canonical = {
                "configured": evidence_repository is not None,
                "latest_decision": None,
                "replay": None,
            }
            if evidence_repository is not None:
                decisions = list(evidence_repository.decisions(limit=1))
                observations = list(evidence_repository.observations(limit=500))
                canonical["latest_decision"] = decisions[0] if decisions else None
                canonical["replay"] = replay_health_state(observations)

            return {
                **health,
                "founder_alert": build_founder_alert(health),
                "canonical_evidence_store": canonical,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"deliverability_provider_unavailable:{type(exc).__name__}",
            ) from exc

    return router
