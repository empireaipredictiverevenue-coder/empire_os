from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.lead_smart_operating_hours import evaluate_buyer_hours


SCHEMA_VERSION = (
    "empire.lead_smart."
    "launch_readiness.v1"
)

# Lead Smart's actual written routing and original caller-ID confirmation.
# An affiliate CallRoutes 403 does not refute a real successful test call.
ROUTE_CONFIRMATION_SOURCE = "gmail:1a145122e620d481"
FIVE_CALL_SCOPE = "docs/evidence/lead_smart_founder_launch_intent_20261011.json"


def _supervised_buyer_confirmation(record: Mapping[str, Any] | None, now: datetime) -> bool:
    if not isinstance(record, Mapping):
        return False
    if (record.get("buyer") != "Lead Smart"
            or record.get("campaign_id") != "CA8278ed3f26e9495b881fe3833174d007"
            or record.get("tracking_number") != "+18883579305"
            or record.get("source_ref") != ROUTE_CONFIRMATION_SOURCE
            or record.get("founder_authority_ref") != FIVE_CALL_SCOPE
            or record.get("buyer_confirmed_direct_route") is not True
            or record.get("buyer_confirmed_original_ani") is not True
            or record.get("founder_witnessed_voice_connection") is not True
            or record.get("independently_proven_admin_api") is not False):
        return False
    # The founder approved the existing bounded test, not an open-ended
    # permanent attestation exception for other campaigns or dates.
    try:
        start = datetime.fromisoformat(str(record["starts_at"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(record["ends_at"]).replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError):
        return False
    return (start.tzinfo is not None and end.tzinfo is not None
            and start.astimezone(timezone.utc).isoformat() == "2026-10-19T15:00:00+00:00"
            and end.astimezone(timezone.utc).isoformat() == "2026-10-19T17:00:00+00:00"
            and start <= now < end)


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
    caller_id_pass_through_verified: bool = False,
    buyer_landing_page_approved: bool = False,
    legal_release_verified: bool = False,
    recording_notice_and_retention_verified: bool = False,
    landing_publication_authorized: bool = False,
    founder_live_traffic_authorized: bool = False,
    pilot_stop_verified: bool = False,
    supervised_buyer_confirmation: Mapping[str, Any] | None = None,
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
        "legal_release_verified": legal_release_verified is True,
        # Releasing a site privacy policy does NOT confirm Ringba/buyer
        # recording consent, access, retention and deletion governance.
        "recording_notice_and_retention_verified": (
            recording_notice_and_retention_verified is True
        ),
        # A launch is never live-ready on approval alone: a bounded pilot
        # needs an independently proven stop mechanism and monitoring owner.
        "pilot_stop_verified": pilot_stop_verified is True,
        "operating_hours_verified": hours["operating_hours_verified"],

        "caller_id_pass_through_verified": (
            caller_id_pass_through_verified is True
        ),

        "tracking_verified":
            tracking_verified,

        "zip_targeting_verified":
            zip_verified,

        "routing_runtime_verified":
            routing_verified,

        "buyer_landing_page_approved": buyer_landing_page_approved is True,

        # Approval is an explicit boolean, never truthiness of external input.
        # In particular, "false" and integer 1 cannot grant launch authority.
        "landing_publication_authorized": landing_publication_authorized is True,

        "founder_live_traffic_authorized": founder_live_traffic_authorized is True,
    }

    # Founder-approved original Direct test may use the named buyer's written
    # route/ANI configuration confirmation and witnessed voice connection.
    # This is NOT administrative Ringba verification or proof of payment.
    buyer_attestation_accepted = (
        _supervised_buyer_confirmation(supervised_buyer_confirmation, now)
        and founder_live_traffic_authorized is True
        and buyer_landing_page_approved is True
        and landing_publication_authorized is True
    )
    attestation_substitutions = (
        frozenset(("routing_runtime_verified", "caller_id_pass_through_verified"))
        if buyer_attestation_accepted else frozenset()
    )
    blockers = [
        name for name, passed in gates.items()
        if passed is not True and name not in attestation_substitutions
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

        "buyer_attested_supervised_route": buyer_attestation_accepted,
        "buyer_route_attestation_ref": (
            ROUTE_CONFIRMATION_SOURCE if buyer_attestation_accepted else None
        ),
        "pilot_admission_substitutions": sorted(attestation_substitutions),
        "independent_route_proven": routing_verified,
        "independent_ani_proven": caller_id_pass_through_verified is True,
        "revenue_verified": False,

        "operating_hours": hours,

        # Distinguish independently confirmed buyer policy from a currently
        # open call window. The live operating-hours gate still REQUIRES BOTH.
        "operating_hours_policy_confirmed": hours["hours_policy_confirmed"],
        "buyer_window_open_now": hours["buyer_window_open_now"],

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
