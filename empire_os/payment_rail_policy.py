"""Canonical EmpireOS payment-rail policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CANONICAL_ASSET = "USDT"
CANONICAL_NETWORK = "BSC"
CANONICAL_CHAIN_ID = 56
RETIRED_RAILS = (
    "SOLANA",
    "USDC",
    "SOLANA_PAY",
    "PHANTOM",
    "ANCHOR",
    "JUPITER",
)


class RetiredPaymentRailError(RuntimeError):
    """Raised when executable code attempts to use a retired payment rail."""


@dataclass(frozen=True)
class PaymentRailStatus:
    asset: str = CANONICAL_ASSET
    network: str = CANONICAL_NETWORK
    chain_id: int = CANONICAL_CHAIN_ID
    execution_authority: str = "none"
    actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_payment_rail() -> dict[str, Any]:
    return PaymentRailStatus().as_dict()


def retired_component(component: str) -> dict[str, Any]:
    name = str(component or "").strip() or "legacy_payment_component"
    return {
        "status": "RETIRED",
        "component": name,
        "reason": "legacy_payment_rail_retired",
        "replacement": "governed_bsc_usdt_payment_flow",
        "asset": CANONICAL_ASSET,
        "network": CANONICAL_NETWORK,
        "chain_id": CANONICAL_CHAIN_ID,
        "execution_allowed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def reject_retired_component(component: str) -> None:
    status = retired_component(component)
    raise RetiredPaymentRailError(
        f"{status['component']}: retired; use "
        f"{CANONICAL_ASSET} on {CANONICAL_NETWORK} "
        f"(chain {CANONICAL_CHAIN_ID}) through payment_governance"
    )


def assert_canonical_rail(asset: str, network: str) -> None:
    if str(asset or "").strip().upper() != CANONICAL_ASSET:
        raise ValueError("canonical settlement asset must be USDT")
    if str(network or "").strip().upper() != CANONICAL_NETWORK:
        raise ValueError("canonical settlement network must be BSC")
