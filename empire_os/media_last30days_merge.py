"""Attach date-validated Last30Days reports to the existing Media OS research pack.

Only public citations are added. This never grants facts, scripts, buyer
acceptance, automatic actions, payment authority or revenue.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.media_last30days_demand import build_last30days_media_candidates


def merge_last30days_reports(
    canonical: Mapping[str, Any],
    raw_reports: list[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(canonical, Mapping)
        or canonical.get("schema_version") != "empire.media.research_candidates.v1"
        or canonical.get("execution_authority") != "none"
        or canonical.get("mode") != "OBSERVE"
        or canonical.get("verified_claim_count") != 0
        or canonical.get("script_ready_count") != 0
        or canonical.get("automatic_script_generation_authorized") is not False
        or canonical.get("public_publish_authorized") is not False
        or canonical.get("actual_revenue") is not False
        or not isinstance(canonical.get("candidates"), list)
        or canonical.get("candidate_count") != len(canonical["candidates"])
    ):
        raise ValueError("unsafe_last30days_canonical_queue")
    output = deepcopy(dict(canonical))
    seen = {c.get("research_id") for c in output["candidates"] if isinstance(c, dict)}
    if len(seen) != len(output["candidates"]):
        raise ValueError("duplicate_canonical_research_id")
    audits: list[dict[str, Any]] = []
    for doc in raw_reports:
        recent = build_last30days_media_candidates(doc, now=now or datetime.now(timezone.utc))
        if not recent["source_available"]:
            audits.append({
                "topic": recent["topic"], "status": recent["source_state"],
                "source_observation_count": 0,
            })
            continue
        status = recent["source_state"]
        if status != "OBSERVED_CANDIDATES_NOT_VERIFIED_DEMAND":
            audits.append({
                "topic": recent["topic"], "status": status,
                "source_observation_count": 0,
            })
            continue
        for pack in recent["candidates"]:
            if (
                pack.get("schema_version") != "empire.media.research_pack.v1"
                or not str(pack.get("research_id", "")).startswith("media-research:last30days:")
                or pack.get("claims") != []
                or pack.get("script_ready") is not False
                or pack.get("automatic_script_generation_authorized") is not False
                or pack.get("public_publish_authorized") is not False
                or pack.get("execution_authority") != "none"
                or not isinstance(pack.get("sources"), list)
                or not pack["sources"]
            ):
                raise ValueError("last30days_unsafe_research_pack")
            if pack["research_id"] not in seen:
                output["candidates"].append(deepcopy(pack))
                seen.add(pack["research_id"])
        audits.append({
            "topic": recent["topic"],
            "status": recent["source_state"],
            "observed_at": recent["observed_at"],
            "source_status": recent["source_status"],
            "source_observation_count": recent["source_observation_count"],
            "verified_claim_count": 0,
            "commercial_buyer_demand_proven": False,
        })
    output["source_available"] = bool(output.get("source_available")) or bool(audits)
    output["candidate_count"] = len(output["candidates"])
    output["source_observation_count"] = sum(
        len(c.get("sources") or []) for c in output["candidates"]
    )
    output["last30days_research_runs"] = audits
    output["verified_claim_count"] = 0
    output["script_ready_count"] = 0
    output["automatic_script_generation_authorized"] = False
    output["public_publish_authorized"] = False
    output["actual_revenue"] = False
    output["execution_authority"] = "none"
    return output
