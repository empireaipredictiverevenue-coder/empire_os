from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.lead_smart_operating_hours import evaluate_buyer_hours


SCHEMA_VERSION = (
    "empire.lead_smart."
    "launch_readiness.v1"
)



def _fresh(timestamp: Any, *, now: datetime, max_age_seconds: int) -> bool:
    if not isinstance(timestamp, str):
        return False
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    age = (now - parsed.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= max_age_seconds


def build_launch_readiness(
    *,
    tracking: Mapping[str, Any],
    zip_gate: Mapping[str, Any],
    routing: Mapping[str, Any],
    operating_hours: Mapping[str, Any] | None = None,
    timezone_confirmation: Mapping[str, Any] | None = None,
    landing_publication_authorized: bool = False,
    founder_live_traffic_authorized: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("launch verification time requires timezone")
    now = now.astimezone(timezone.utc)

    tracking_verified = (
        tracking.get("state") == "VERIFIED"
        and tracking.get(
            "tracking_verified"
        )
        is True
        and _fresh(tracking.get("verified_at"), now=now, max_age_seconds=3600)
        and _fresh(tracking.get("source_observed_at"), now=now, max_age_seconds=3600)
    )

    zip_verified = (
        zip_gate.get(
            "zip_targeting_gate_verified"
        )
        is True
        and zip_gate.get(
            "zip_coverage_activation_verified"
        )
        is True
        and zip_gate.get("source_fresh_for_targeting") is True
        and _fresh(zip_gate.get("source_observed_at"), now=now, max_age_seconds=21600)
        and _fresh(
            (zip_gate.get("verified_freshness") or {}).get("source_newest_last_updated"),
            now=now,
            max_age_seconds=108000,
        )
    )

    routing_verified = (
        routing.get(
            "routing_runtime_verified"
        )
        is True
        and _fresh(routing.get("observed_at"), now=now, max_age_seconds=3600)
    )

    hours = evaluate_buyer_hours(
        operating_hours,
        timezone_confirmation,
        now=now,
    )

    gates = {
        "operating_hours_verified": hours["operating_hours_verified"],

        "tracking_verified":
            tracking_verified,

        "zip_targeting_verified":
            zip_verified,

        "routing_runtime_verified":
            routing_verified,

        "landing_publication_authorized":
            bool(
                landing_publication_authorized
            ),

        "founder_live_traffic_authorized":
            bool(
                founder_live_traffic_authorized
            ),
    }

    blockers = [
        name
        for name, passed
        in gates.items()
        if passed is not True
    ]

    ready = not blockers

    return {
        "schema_version":
            SCHEMA_VERSION,

        "mode":
            (
                "READY"
                if ready
                else "PREACTIVATION"
            ),

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "gates":
            gates,

        "operating_hours": hours,

        "blockers":
            blockers,

        "launch_ready":
            ready,

        "call_cta_enabled":
            ready,

        "organic_traffic_authorized":
            ready,

        # No provider configuration mutation is
        # performed by this readiness object.
        "provider_route_mutation":
            False,

        "deployment_performed":
            False,

        "execution_authority":
            (
                "LIVE_TRAFFIC"
                if ready
                else "NONE"
            ),
    }
