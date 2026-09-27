"""Read-only Founder status for Batch 1 business agents."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from empire_os.buyer_reply_operations_agent import buyer_reply_ops_status
from empire_os.deliverability_sender_reputation_agent import (
    deliverability_agent_status,
)
from empire_os.source_reliability_agent import (
    source_reliability_agent_status,
)


def build_business_agents_status() -> dict[str, Any]:
    return {
        "schema_version": "empire.founder-business-agents.v1",
        "buyer_reply_operations": buyer_reply_ops_status(),
        "deliverability_sender_reputation": deliverability_agent_status(),
        "source_reliability": source_reliability_agent_status(),
        "architecture_ref": "docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md",
        "read_only": True,
        "execution_authority": "none",
    }


def create_founder_business_agents_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-business-agents",
        tags=["founder-business-agents"],
    )

    @router.get("/status")
    def status():
        return build_business_agents_status()

    return router
