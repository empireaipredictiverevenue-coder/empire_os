"""Voice routing policy for EmpireOS.

The legacy pay-per-call switchboard is intentionally parked. This module is
the only place Voice Lab learns whether that route is eligible for activation.
"""
from __future__ import annotations

import os
from typing import Any


PARKED = "PARKED"
READY_FOR_REVIEW = "READY_FOR_REVIEW"
ACTIVE = "ACTIVE"


def switchboard_status() -> dict[str, Any]:
    mode = str(
        os.getenv("EMPIRE_PPC_SWITCHBOARD_MODE") or PARKED
    ).strip().upper()
    if mode not in {PARKED, READY_FOR_REVIEW, ACTIVE}:
        mode = PARKED

    url = str(
        os.getenv(
            "EMPIRE_PPC_SWITCHBOARD_URL",
            "http://127.0.0.1:9100",
        )
    ).strip()

    route_enabled = (
        mode == ACTIVE
        and str(
            os.getenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED") or ""
        ).strip().lower() in {"1", "true", "yes", "on"}
    )

    return {
        "mode": mode,
        "url": url,
        "route_enabled": route_enabled,
        "canonical_transport": "vonage",
        "canonical_database": "supabase",
        "canonical_payment_rail": "usdt_bsc",
        "legacy_module_present": True,
        "legacy_activation_allowed": False,
        "execution_allowed": False if not route_enabled else True,
        "reason": (
            "legacy_ppc_switchboard_parked_pending_canonical_refactor"
            if not route_enabled
            else "explicit_route_activation_present"
        ),
    }


def should_route_to_switchboard() -> bool:
    return switchboard_status()["execution_allowed"] is True
