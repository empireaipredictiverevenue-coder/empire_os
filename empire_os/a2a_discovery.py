"""Read-only Phase 6 A2A commerce discovery contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

A2A_DISCOVERY_VERSION = "a2a-commerce-discovery-v1"


@dataclass(frozen=True)
class CommerceCapability:
    key: str
    description: str
    authentication_required: bool = True
    human_approval_required: bool = True
    execution_exposed: bool = False
    payment_exposed: bool = False
    allocation_exposed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


COMMERCE_CAPABILITIES: tuple[CommerceCapability, ...] = (
    CommerceCapability(
        "commerce.quote.request",
        "Request a governed commercial quote after authenticated agent identity.",
    ),
    CommerceCapability(
        "commerce.negotiation.start",
        "Open a governed negotiation task without autonomous commitment.",
    ),
    CommerceCapability(
        "commerce.task.create",
        "Create a governed A2A commercial task for later approval and execution.",
    ),
)
def commerce_discovery_manifest(
    *,
    public_base_url: str,
    public_capability_names: list[str],
) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "version": A2A_DISCOVERY_VERSION,
        "agent": {
            "name": "Empire Astra Intelligence Agent",
            "base_url": base,
        },
        "public_discovery": {
            "authentication_required": False,
            "capabilities": list(public_capability_names),
            "message_endpoint": f"{base}/a2a/v1/message:send",
        },
        "commercial_discovery": {
            "authentication_required": True,
            "authentication_status": "not_activated",
            "governance": "explicit approval required before consequential action",
            "capabilities": [
                capability.as_dict()
                for capability in COMMERCE_CAPABILITIES
            ],
        },
        "privileged_actions_exposed": False,
        "payments_exposed": False,
        "allocations_exposed": False,
    }
