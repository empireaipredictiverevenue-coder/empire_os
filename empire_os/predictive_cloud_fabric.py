from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ExecutionAuthority(StrEnum):
    OBSERVE = "observe"
    PROPOSE = "propose"
    EXECUTE_BOUNDED = "execute_bounded"


class TenantContextSource(StrEnum):
    NONE = "none"
    AUTHENTICATED = "authenticated"
    SYSTEM = "system"


FOUNDER_GATED_ACTIONS = frozenset({
    "execute:db_migration",
    "execute:destructive_db",
    "execute:live_outbound",
    "execute:paid_traffic",
    "execute:spend",
    "execute:fund_movement",
    "execute:mainnet",
    "execute:binding_terms",
    "execute:revenue_recognition",
    "execute:authority_expansion",
})


@dataclass(frozen=True)
class EvidenceRef:
    ref: str
    kind: str
    digest: str | None = None

    def __post_init__(self) -> None:
        if not self.ref.strip():
            raise ValueError("evidence ref required")
        if not self.kind.strip():
            raise ValueError("evidence kind required")


@dataclass(frozen=True)
class EconomicTrace:
    expected_revenue_cents: int | None = None
    realized_revenue_cents: int | None = None
    buyer_payout_cents: int | None = None
    traffic_cost_cents: int | None = None
    ai_cost_cents: int | None = None
    gross_contribution_cents: int | None = None
    reinvestable_cash_cents: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "expected_revenue_cents",
            "realized_revenue_cents",
            "buyer_payout_cents",
            "traffic_cost_cents",
            "ai_cost_cents",
            "gross_contribution_cents",
            "reinvestable_cash_cents",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0 or unavailable")


@dataclass(frozen=True)
class PredictiveCloudFabricContext:
    trace_id: str
    authority: ExecutionAuthority = ExecutionAuthority.OBSERVE

    tenant_id: str | None = None
    tenant_source: TenantContextSource = TenantContextSource.NONE

    account_id: str | None = None
    opportunity_id: str | None = None
    buyer_id: str | None = None
    product_id: str | None = None
    campaign_id: str | None = None
    lead_id: str | None = None
    conversation_id: str | None = None

    approved_gates: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id required")

        if self.tenant_id is not None and self.tenant_source not in {
            TenantContextSource.AUTHENTICATED,
            TenantContextSource.SYSTEM,
        }:
            raise ValueError(
                "tenant identity must come from authenticated/system context"
            )

        if (
            self.tenant_source is not TenantContextSource.NONE
            and self.tenant_id is None
        ):
            raise ValueError("tenant_source requires tenant_id")


@dataclass(frozen=True)
class FabricCapability:
    name: str
    allowed_actions: frozenset[str]

    def allows(
        self,
        action: str,
        *,
        context: PredictiveCloudFabricContext,
    ) -> bool:
        if action not in self.allowed_actions:
            return False

        if (
            action in FOUNDER_GATED_ACTIONS
            and action not in context.approved_gates
        ):
            return False

        if context.authority is ExecutionAuthority.OBSERVE:
            return not (
                action.startswith("write:")
                or action.startswith("execute:")
            )

        if context.authority is ExecutionAuthority.PROPOSE:
            return not action.startswith("execute:")

        return True


@dataclass(frozen=True)
class FabricRecoveryState:
    workflow_id: str
    checkpoint: str
    attempt: int = 0
    recoverable: bool = True
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.workflow_id.strip():
            raise ValueError("workflow_id required")
        if not self.checkpoint.strip():
            raise ValueError("checkpoint required")
        if self.attempt < 0:
            raise ValueError("attempt must be >= 0")


class FabricAdapter(Protocol):
    @property
    def adapter_name(self) -> str:
        ...
