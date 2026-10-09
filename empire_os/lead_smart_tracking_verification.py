from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
import re


SOURCE_SCHEMA = (
    "empire.lead_smart."
    "ringba_tracking_object_observation.v1"
)

SCHEMA_VERSION = (
    "empire.lead_smart."
    "tracking_verification.v1"
)

EXPECTED_CAMPAIGN_ID = (
    "CA8278ed3f26e9495b881fe3833174d007"
)

EXPECTED_TRACKING_NUMBER = (
    "+18883579305"
)

# Provider-object evidence must be recent when the
# verification state is materialized.
MAX_SOURCE_AGE_SECONDS = 60 * 60


def _parse_time(
    value: str,
) -> datetime:
    result = datetime.fromisoformat(
        str(value).replace(
            "Z",
            "+00:00",
        )
    )

    if result.tzinfo is None:
        raise ValueError(
            "observed_at must be "
            "timezone-aware"
        )

    return result.astimezone(
        timezone.utc
    )


def _digits(
    value: Any,
) -> str:
    return re.sub(
        r"\D",
        "",
        str(value or ""),
    )


def build_tracking_verification(
    observation: Mapping[str, Any],
    *,
    source_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Promote provider-observed number↔campaign binding
    into TRACKING VERIFICATION ONLY.

    This does not prove:
      - call routing works
      - qualification works
      - payout works
      - ZIP activation
      - traffic authorization
      - revenue
    """

    data = dict(
        observation or {}
    )

    if (
        data.get(
            "schema_version"
        )
        != SOURCE_SCHEMA
    ):
        raise ValueError(
            "unexpected tracking "
            "observation schema"
        )

    if data.get("mode") != "OBSERVE":
        raise ValueError(
            "tracking observation "
            "must be OBSERVE"
        )

    if data.get("provider") != "Ringba":
        raise ValueError(
            "provider must be Ringba"
        )

    if (
        data.get("buyer")
        != "Lead Smart"
    ):
        raise ValueError(
            "buyer mismatch"
        )

    if (
        data.get("vertical")
        != "Roofing"
    ):
        raise ValueError(
            "vertical mismatch"
        )

    if (
        data.get("campaign_id")
        != EXPECTED_CAMPAIGN_ID
    ):
        raise ValueError(
            "campaign mismatch"
        )

    if (
        _digits(
            data.get(
                "tracking_number"
            )
        )
        != _digits(
            EXPECTED_TRACKING_NUMBER
        )
    ):
        raise ValueError(
            "tracking number mismatch"
        )

    observed_at = _parse_time(
        data.get("observed_at")
    )

    now = (
        now
        or datetime.now(
            timezone.utc
        )
    )

    if now.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware"
        )

    now = now.astimezone(
        timezone.utc
    )

    age_seconds = int(
        (
            now - observed_at
        ).total_seconds()
    )

    if age_seconds < 0:
        raise ValueError(
            "provider evidence "
            "cannot be from future"
        )

    if (
        age_seconds
        > MAX_SOURCE_AGE_SECONDS
    ):
        raise ValueError(
            "provider tracking "
            "evidence is stale"
        )

    source_hash = str(
        source_sha256 or ""
    ).strip().lower()

    if re.fullmatch(
        r"[0-9a-f]{64}",
        source_hash,
    ) is None:
        raise ValueError(
            "valid source sha256 required"
        )

    direct = (
        data.get(
            "direct_campaign_binding"
        )
        is True
    )

    inbound = (
        data.get(
            "inbound_reference_binding"
        )
        is True
    )

    if not (
        direct or inbound
    ):
        raise ValueError(
            "no provider binding path"
        )

    if (
        data.get(
            "provider_binding_verified"
        )
        is not True
    ):
        raise ValueError(
            "provider binding not verified"
        )

    if (
        data.get(
            "tracking_verification_candidate"
        )
        is not True
    ):
        raise ValueError(
            "tracking verification "
            "candidate absent"
        )

    # Observer itself must have remained non-mutating.
    if (
        data.get(
            "tracking_verified_change"
        )
        is not False
    ):
        raise ValueError(
            "source observer mutated "
            "tracking authority"
        )

    if (
        data.get(
            "routing_verified_change"
        )
        is not False
    ):
        raise ValueError(
            "source observer mutated "
            "routing authority"
        )

    if (
        data.get(
            "routing_enabled"
        )
        is not False
        or data.get(
            "traffic_enabled"
        )
        is not False
    ):
        raise ValueError(
            "source evidence carries "
            "unexpected live authority"
        )

    if (
        data.get(
            "execution_authority"
        )
        != "NONE"
    ):
        raise ValueError(
            "source execution authority "
            "must be NONE"
        )

    verification_path = (
        "DIRECT_CAMPAIGN_OBJECT"
        if direct
        else "NUMBER_INBOUND_REFERENCE"
    )

    return {
        "schema_version":
            SCHEMA_VERSION,

        "state":
            "VERIFIED",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "provider":
            "Ringba",

        "campaign_id":
            EXPECTED_CAMPAIGN_ID,

        "tracking_number":
            EXPECTED_TRACKING_NUMBER,

        "verification_scope":
            "NUMBER_TO_CAMPAIGN_BINDING",

        "verification_path":
            verification_path,

        "evidence_class":
            "AUTHENTICATED_PROVIDER_OBJECT",

        "source_observed_at":
            observed_at.isoformat(),

        "verified_at":
            now.isoformat(),

        "source_age_seconds":
            age_seconds,

        "source_max_age_seconds":
            MAX_SOURCE_AGE_SECONDS,

        "source_sha256":
            source_hash,

        "tracking_number_assigned":
            True,

        "tracking_verified":
            True,

        # Explicit non-implications.
        "routing_verified":
            False,

        "zip_coverage_activation_verified":
            False,

        "routing_enabled":
            False,

        "traffic_enabled":
            False,

        "commercial_activation":
            False,

        "revenue_recognized":
            False,

        "provider_call_observed":
            False,

        "provider_payout_observed":
            False,

        "execution_authority":
            "NONE",
    }
