from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


DEFAULT_SNAPSHOT_PATH = Path(
    "runtime/revenue/lead_smart/coverage/latest.json"
)

# V1 freshness contract:
#
# The external source states that coverage is refreshed daily.
# We permit a 30-hour source age for analytical targeting so an
# overnight refresh boundary cannot create a false stale condition.
#
# The locally-owned observation itself must be <= 6 hours old.
#
# IMPORTANT:
# Freshness permits ANALYSIS only. It does not grant call routing,
# traffic, tracking verification or commercial activation.
SOURCE_TARGETING_MAX_AGE_SECONDS = 30 * 60 * 60
LOCAL_SNAPSHOT_MAX_AGE_SECONDS = 6 * 60 * 60


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def load_snapshot(
    path: Path = DEFAULT_SNAPSHOT_PATH,
) -> dict[str, Any]:
    data = json.loads(path.read_text())

    if (
        data.get("schema_version")
        != "empire.lead_smart.coverage_snapshot.v1"
    ):
        raise RuntimeError(
            "unexpected Lead Smart coverage snapshot schema"
        )

    if data.get("mode") != "OBSERVE":
        raise RuntimeError(
            "Lead Smart coverage snapshot must be OBSERVE"
        )

    source = data.get("source") or {}

    if source.get("table") != "offer_bids":
        raise RuntimeError(
            "unexpected Lead Smart coverage source table"
        )

    if (
        source.get("semantics")
        != "TARGETING_GUIDANCE_ONLY"
    ):
        raise RuntimeError(
            "coverage source semantics are not fail-closed"
        )

    if source.get("payout_guaranteed") is not False:
        raise RuntimeError(
            "coverage payout must not be treated as guaranteed"
        )

    return data


def freshness(
    snapshot: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    now = now.astimezone(timezone.utc)

    observed_at = _parse_time(
        snapshot["observed_at"]
    )

    newest_source = _parse_time(
        snapshot["coverage"][
            "source_newest_last_updated"
        ]
    )

    local_age = max(
        0,
        int(
            (now - observed_at)
            .total_seconds()
        ),
    )

    source_age = max(
        0,
        int(
            (now - newest_source)
            .total_seconds()
        ),
    )

    local_fresh = (
        local_age
        <= LOCAL_SNAPSHOT_MAX_AGE_SECONDS
    )

    source_fresh = (
        source_age
        <= SOURCE_TARGETING_MAX_AGE_SECONDS
    )

    return {
        "observed_at":
            observed_at.isoformat(),
        "source_newest_last_updated":
            newest_source.isoformat(),

        "local_snapshot_age_seconds":
            local_age,

        "source_age_seconds":
            source_age,

        "local_snapshot_max_age_seconds":
            LOCAL_SNAPSHOT_MAX_AGE_SECONDS,

        "source_targeting_max_age_seconds":
            SOURCE_TARGETING_MAX_AGE_SECONDS,

        "local_snapshot_fresh":
            local_fresh,

        "source_fresh_for_targeting":
            source_fresh,

        "fresh_for_targeting_analysis":
            local_fresh and source_fresh,

        # Freshness alone can NEVER authorize live use.
        "freshness_grants_execution_authority":
            False,
    }


def _validate_zip(zip_code: str) -> str:
    value = str(zip_code).strip()

    if re.fullmatch(r"\d{5}", value) is None:
        raise ValueError(
            f"ZIP must be exactly five digits: {zip_code!r}"
        )

    return value


def rows_by_zip(
    snapshot: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for row in snapshot.get("rows") or []:
        zip_code = _validate_zip(row["zip"])

        if zip_code in result:
            raise RuntimeError(
                f"ambiguous duplicate ZIP row: {zip_code}"
            )

        result[zip_code] = row

    return result


def lookup_zip(
    snapshot: dict[str, Any],
    zip_code: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    zip_code = _validate_zip(zip_code)

    index = rows_by_zip(snapshot)
    row = index.get(zip_code)

    state = freshness(
        snapshot,
        now=now,
    )

    authority = snapshot.get("authority") or {}

    observed = row is not None

    top_payout = (
        float(row["top_payout"])
        if row
        and row.get("top_payout") is not None
        else None
    )

    duration_payout = (
        float(row["duration_payout"])
        if row
        and row.get("duration_payout") is not None
        else None
    )

    cpl_payout = (
        float(row["cpl_payout"])
        if row
        and row.get("cpl_payout") is not None
        else None
    )

    targeting_candidate = (
        observed
        and state[
            "fresh_for_targeting_analysis"
        ]
        and top_payout is not None
    )

    activation_gates = {
        "zip_observed":
            observed,

        "fresh_for_targeting_analysis":
            state[
                "fresh_for_targeting_analysis"
            ],

        "zip_coverage_activation_verified":
            authority.get(
                "zip_coverage_activation_verified"
            )
            is True,

        "tracking_verified":
            authority.get(
                "tracking_verified"
            )
            is True,

        "routing_verified":
            authority.get(
                "routing_verified"
            )
            is True,

        "routing_enabled":
            authority.get(
                "routing_enabled"
            )
            is True,

        "traffic_enabled":
            authority.get(
                "traffic_enabled"
            )
            is True,
    }

    live_route_eligible = all(
        activation_gates.values()
    )

    return {
        "schema_version":
            "empire.lead_smart.zip_intelligence.v1",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "zip":
            zip_code,

        "coverage_observed":
            observed,

        "targeting_candidate":
            targeting_candidate,

        "live_route_eligible":
            live_route_eligible,

        "observed_offer_name":
            row.get("offer_name")
            if row else None,

        "observed_duration_payout":
            duration_payout,

        "observed_cpl_payout":
            cpl_payout,

        "observed_top_payout":
            top_payout,

        "source_last_updated":
            row.get("last_updated")
            if row else None,

        "freshness":
            state,

        "activation_gates":
            activation_gates,

        "evidence_class":
            "OBSERVED_TARGETING_GUIDANCE",

        "payout_guaranteed":
            False,

        "execution_authority":
            "NONE",
    }


def rank_observed_zips(
    snapshot: dict[str, Any],
    *,
    limit: int = 25,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be >= 1")

    state = freshness(
        snapshot,
        now=now,
    )

    if not state[
        "fresh_for_targeting_analysis"
    ]:
        return []

    candidates = []

    for row in snapshot.get("rows") or []:
        payout = row.get("top_payout")

        if payout is None:
            continue

        candidates.append({
            "zip": row["zip"],
            "city": row.get("city"),
            "state": row.get("state"),
            "offer_name":
                row.get("offer_name"),
            "observed_top_payout":
                float(payout),
            "observed_duration_payout":
                (
                    float(row["duration_payout"])
                    if row.get(
                        "duration_payout"
                    ) is not None
                    else None
                ),
            "observed_cpl_payout":
                (
                    float(row["cpl_payout"])
                    if row.get(
                        "cpl_payout"
                    ) is not None
                    else None
                ),
            "last_updated":
                row.get("last_updated"),
        })

    candidates.sort(
        key=lambda row: (
            -row["observed_top_payout"],
            row["zip"],
        )
    )

    return candidates[:limit]


def payout_contract_drift(
    snapshot: dict[str, Any],
    *,
    canonical_min: float,
    canonical_max: float,
) -> dict[str, Any]:
    values = [
        float(row["top_payout"])
        for row in snapshot.get("rows") or []
        if row.get("top_payout") is not None
    ]

    below = [
        value
        for value in values
        if value < canonical_min
    ]

    above = [
        value
        for value in values
        if value > canonical_max
    ]

    return {
        "schema_version":
            "empire.lead_smart.payout_drift.v1",

        "canonical_offer_min":
            canonical_min,

        "canonical_offer_max":
            canonical_max,

        "observed_targeting_min":
            min(values)
            if values else None,

        "observed_targeting_max":
            max(values)
            if values else None,

        "below_canonical_min_count":
            len(below),

        "above_canonical_max_count":
            len(above),

        "drift_observed":
            bool(below or above),

        "canonical_contract_overwritten":
            False,

        "interpretation":
            "TARGETING_GUIDANCE_CONTRACT_DRIFT",

        "execution_authority":
            "NONE",
    }


def change_intelligence(
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    delta = snapshot.get("delta") or {}

    return {
        "schema_version":
            "empire.lead_smart.coverage_change.v1",

        "baseline":
            delta.get("baseline"),

        "source_changed":
            delta.get("source_changed"),

        "zip_added_count":
            delta.get("zip_added_count"),

        "zip_removed_count":
            delta.get("zip_removed_count"),

        "top_payout_changed_zip_count":
            delta.get(
                "top_payout_changed_zip_count"
            ),

        "source_hash":
            snapshot.get("source_hash"),

        "execution_authority":
            "NONE",
    }
