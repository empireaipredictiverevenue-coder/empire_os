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

    route_requested = (
        mode == ACTIVE
        and str(
            os.getenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED") or ""
        ).strip().lower() in {"1", "true", "yes", "on"}
    )
    canonical_ready = str(
        os.getenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    route_enabled = bool(route_requested and canonical_ready)

    return {
        "mode": mode,
        "url": url,
        "route_requested": route_requested,
        "canonical_refactor_ready": canonical_ready,
        "route_enabled": route_enabled,
        "canonical_transport": "vonage",
        "canonical_database": "supabase",
        "canonical_payment_rail": "usdt_bsc",
        "legacy_module_present": True,
        "legacy_activation_allowed": False,
        "execution_allowed": route_enabled,
        "reason": (
            "canonical_refactor_and_route_gate_approved"
            if route_enabled
            else "legacy_ppc_switchboard_parked_pending_canonical_refactor"
        ),
    }


def should_route_to_switchboard() -> bool:
    return switchboard_status()["execution_allowed"] is True
