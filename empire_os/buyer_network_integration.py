from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from empire_os.buyer_network_intelligence import (
    assess_candidate,
    assess_lane_health,
    assess_supply_fit,
    bounded_test_plan,
    interpret_reply,
    observed_unit_economics,
)


EXISTING_STACK = (
    "empire_os.buyer_discovery",
    "empire_os.buyer_acquisition_scout",
    "empire_os.buyer_scout",
    "empire_os.buyer_demand_graph",
    "empire_os.buyer_capacity_learning",
    "empire_os.buyer_capacity_readiness",
    "empire_os.buyer_commercial_terms_intake",
    "empire_os.buyer_reply_operations_agent",
    "empire_os.buyer_call_economics",
    "empire_os.buyer_recovery",
    "empire_os.buyer_supply_policy",
    "empire_os.buyer_supply_review",
    "empire_os.economic_memory",
    "empire_os.opportunity_radar",
    "empire_os.department_cycle",
)


@dataclass(frozen=True)
class IntegrationStatus:
    ready: bool
    loaded_modules: tuple[str, ...]
    missing_modules: tuple[str, ...]
    authority: str = "OBSERVE"


def integration_status() -> IntegrationStatus:

    loaded = []
    missing = []

    for name in EXISTING_STACK:

        try:
            import_module(name)

        except Exception:
            missing.append(name)

        else:
            loaded.append(name)

    return IntegrationStatus(
        ready=not missing,
        loaded_modules=tuple(loaded),
        missing_modules=tuple(missing),
    )


class BuyerNetworkIntegration:
    """
    Additive adapter over the existing EmpireOS buyer architecture.

    It does not replace or patch existing modules.
    """

    authority = "OBSERVE"

    @staticmethod
    def candidate(**kwargs):
        return assess_candidate(**kwargs)

    @staticmethod
    def supply_fit(**kwargs):
        return assess_supply_fit(**kwargs)

    @staticmethod
    def reply(text: str):
        return interpret_reply(text)

    @staticmethod
    def economics(events):
        return observed_unit_economics(events)

    @staticmethod
    def lane_health(**kwargs):
        return assess_lane_health(**kwargs)

    @staticmethod
    def bounded_test(**kwargs):
        return bounded_test_plan(**kwargs)
