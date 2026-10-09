from __future__ import annotations

import re
from typing import Any, Mapping


SNAPSHOT_SCHEMA = (
    "empire.lead_smart.coverage_snapshot.v1"
)

INTELLIGENCE_SCHEMA = (
    "empire.lead_smart.coverage_intelligence.v1"
)

SCHEMA_VERSION = (
    "empire.lead_smart.zip_targeting_gate.v1"
)


def build_zip_targeting_gate(
    *,
    snapshot: Mapping[str, Any],
    intelligence: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Verify Empire's PRE-CALL ZIP targeting gate.

    Important:
      covered here means present in Lead Smart's current
      targeting-guidance dataset.

      It does NOT guarantee:
        - buyer acceptance,
        - live route availability,
        - qualification,
        - payout,
        - revenue.
    """

    source = dict(snapshot or {})
    intel = dict(intelligence or {})

    if (
        source.get("schema_version")
        != SNAPSHOT_SCHEMA
    ):
        raise ValueError(
            "unexpected coverage snapshot schema"
        )

    if source.get("mode") != "OBSERVE":
        raise ValueError(
            "coverage snapshot must be OBSERVE"
        )

    provenance = dict(
        source.get("source") or {}
    )

    if (
        provenance.get("semantics")
        != "TARGETING_GUIDANCE_ONLY"
    ):
        raise ValueError(
            "coverage semantics must remain "
            "TARGETING_GUIDANCE_ONLY"
        )

    if (
        provenance.get("payout_guaranteed")
        is not False
    ):
        raise ValueError(
            "coverage must not claim "
            "guaranteed payout"
        )

    authority = dict(
        source.get("authority") or {}
    )

    if (
        authority.get(
            "zip_coverage_observed"
        )
        is not True
    ):
        raise ValueError(
            "ZIP coverage has not been observed"
        )

    if (
        authority.get(
            "execution_authority"
        )
        != "NONE"
    ):
        raise ValueError(
            "source must not carry "
            "execution authority"
        )

    if (
        intel.get("schema_version")
        != INTELLIGENCE_SCHEMA
    ):
        raise ValueError(
            "unexpected coverage intelligence schema"
        )

    if intel.get("mode") != "OBSERVE":
        raise ValueError(
            "coverage intelligence must "
            "remain OBSERVE"
        )

    freshness = dict(
        intel.get("freshness") or {}
    )

    if (
        freshness.get(
            "fresh_for_targeting_analysis"
        )
        is not True
    ):
        raise ValueError(
            "coverage source is stale "
            "for targeting"
        )

    rows = list(
        source.get("rows") or []
    )

    if not rows:
        raise ValueError(
            "coverage rows required"
        )

    zips: list[str] = []

    for index, row in enumerate(rows):
        if not isinstance(
            row,
            Mapping,
        ):
            raise ValueError(
                f"coverage row {index} invalid"
            )

        zip_code = str(
            row.get("zip") or ""
        ).strip()

        if (
            re.fullmatch(
                r"\d{5}",
                zip_code,
            )
            is None
        ):
            raise ValueError(
                f"invalid ZIP at row {index}"
            )

        if (
            row.get("offer_key")
            != "roofing"
        ):
            raise ValueError(
                f"unexpected offer at row {index}"
            )

        zips.append(
            zip_code
        )

    unique = sorted(
        set(zips)
    )

    if len(unique) != len(zips):
        raise ValueError(
            "duplicate ZIP rows detected"
        )

    if len(unique) != 28040:
        raise ValueError(
            "current observed roofing ZIP "
            f"count mismatch: {len(unique)}"
        )

    return {
        "schema_version":
            SCHEMA_VERSION,

        "mode":
            "PREACTIVATION",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "offer_key":
            "roofing",

        "source_semantics":
            "TARGETING_GUIDANCE_ONLY",

        "source_observed_at":
            source.get(
                "observed_at"
            ),

        "source_hash":
            source.get(
                "source_hash"
            ),

        "source_fresh_for_targeting":
            True,

        "zip_count":
            len(unique),

        "zips":
            unique,

        # This verifies our own fail-closed
        # targeting control, not the buyer's
        # downstream commercial decision.
        "zip_targeting_gate_verified":
            True,

        "zip_coverage_activation_verified":
            True,

        "activation_scope":
            "EMPIRE_PRECALL_ZIP_GATE",

        "noncovered_zip_call_cta_allowed":
            False,

        "covered_zip_call_cta_may_be_prepared":
            True,

        "provider_runtime_route_verified":
            False,

        "provider_payout_guaranteed":
            False,

        "qualification_guaranteed":
            False,

        "revenue_guaranteed":
            False,

        "routing_enabled":
            False,

        "traffic_enabled":
            False,

        "commercial_activation":
            False,

        "execution_authority":
            "NONE",
    }
