"""Bounded first-party runtime observation for three already-built EmpireOS tasks.

A successful observation is NOT commercial proof, checklist closure, or a new
service. Run only on an explicit bounded verification action; not on each
department cycle, so observation does not cause repeated agent/model work.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request

SCHEMA = "empire.completion.observed-runtime-proof.v1"
OBSERVE_MAX_AGE = timedelta(hours=6)
BODY_MAX = 2_000_000
ORIGIN = "http://127.0.0.1:8766"
TASKS = {
    "Feed validated candidates into Astra workstream ranking": "astra_ranking",
    "Expose full Radar / research / blockers / opportunity lifecycle in Founder Console": "founder_radar",
    "Daily Results: what AI found, researched, advanced, blocked, proved and learned": "daily_results",
}


class RuntimeObservationError(ValueError):
    """Fail closed on stale, unbound or unverifiable runtime evidence."""


def _stamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 48:
        raise RuntimeObservationError("missing_or_invalid_source_timestamp")
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeObservationError("invalid_source_timestamp") from exc
    if x.tzinfo is None or x.utcoffset() is None:
        raise RuntimeObservationError("naive_source_timestamp")
    return x.astimezone(timezone.utc)


def _fresh(value: Any, *, now: datetime) -> datetime:
    stamped = _stamp(value)
    delta = now - stamped
    if delta < -timedelta(minutes=2) or delta > OBSERVE_MAX_AGE:
        raise RuntimeObservationError("stale_or_future_runtime_source")
    return stamped


def _read(root: Path, name: str) -> tuple[dict[str, Any], str]:
    path = root / "runtime" / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > BODY_MAX:
        raise RuntimeObservationError("runtime_snapshot_missing_or_unbounded")
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeObservationError("runtime_snapshot_not_json") from exc
    if not isinstance(data, dict):
        raise RuntimeObservationError("runtime_snapshot_not_object")
    return data, sha256(raw).hexdigest()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeObservationError("unexpected_local_api_redirect")


def _localhost_get(path: str) -> Mapping[str, Any]:
    if path not in {
        "/v1/founder-dashboard/overview",
        "/v1/founder-daily-results/latest",
    }:
        raise RuntimeObservationError("unsupported_local_api_route")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(Request(ORIGIN + path, headers={"Accept": "application/json"}), timeout=4) as response:
            if response.status != 200:
                raise RuntimeObservationError("founder_api_not_200")
            raw = response.read(BODY_MAX + 1)
    except (TimeoutError, OSError, ValueError) as exc:
        raise RuntimeObservationError("founder_api_unavailable") from exc
    if len(raw) > BODY_MAX:
        raise RuntimeObservationError("founder_api_response_unbounded")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeObservationError("founder_api_not_json") from exc
    if not isinstance(data, Mapping):
        raise RuntimeObservationError("founder_api_not_object")
    return data


def _safe_observe(x: Mapping[str, Any], *, schema: str | None = None) -> None:
    if (schema is not None and x.get("schema_version") != schema
            or x.get("execution_authority") != "none"):
        raise RuntimeObservationError("unsupported_source_authority_or_schema")


def observe_existing_runtime(
    repo_root: str | Path,
    task: str,
    *,
    now: datetime | None = None,
    fetch_local: Callable[[str], Mapping[str, Any]] = _localhost_get,
) -> dict[str, Any]:
    """Proof of feature-serving/read-only behaviour, never business results."""
    if task not in TASKS:
        raise RuntimeObservationError("task_has_no_existing_runtime_observer")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise RuntimeObservationError("observer_clock_must_be_aware")
    clock = clock.astimezone(timezone.utc)
    root = Path(repo_root).resolve()
    lane = TASKS[task]
    evidence: list[str] = []
    sources: dict[str, str] = {}

    if lane in ("astra_ranking", "founder_radar"):
        router, digest = _read(root, "opportunity_factory/evidence_routes_latest.json")
        sources["router"] = digest
        _safe_observe(router, schema="empire.opportunity_evidence_routes.v1")
        if (router.get("mode") != "OBSERVE"
                or router.get("automatic_external_execution_allowed") is not False):
            raise RuntimeObservationError("router_not_observe_only")
        router_at = _fresh(router.get("generated_at"), now=clock)
        history = router.get("history")
        if (not isinstance(history, Mapping)
                or history.get("schema_version") != "empire.opportunity_evidence_history.v1"
                or history.get("mode") != "OBSERVE"
                or history.get("execution_authority") != "none"
                or history.get("automatic_external_execution_allowed") is not False
                or history.get("commercial_stage_independently_verified") is not False
                or history.get("previous_stage_never_promoted") is not True
                or _stamp(history.get("generated_at")) != router_at):
            raise RuntimeObservationError("current_history_unverified")
        count = router.get("opportunity_count")
        if (type(count) is not int or not 0 <= count <= 500
                or history.get("active_identity_count") != count):
            raise RuntimeObservationError("history_count_not_bound")
        evidence.append("runtime:router_sha256_" + digest)

    if lane == "astra_ranking":
        executive, digest = _read(root, "astra/executive_latest.json")
        sources["astra"] = digest
        _safe_observe(executive, schema="empire.astra.executive.v2")
        exec_at = _fresh(executive.get("generated_at"), now=clock)
        rank = executive.get("validated_workstream_ranking")
        if (not isinstance(rank, Mapping)
                or rank.get("schema_version") != "empire.astra.validated_workstream_ranking.v1"
                or rank.get("status") != "RANKED_FROM_CURRENT_DERIVED_VALIDATION"
                or rank.get("mode") != "OBSERVE"
                or rank.get("execution_authority") != "none"
                or rank.get("commercial_authority") != "none"
                or rank.get("automatic_external_execution_allowed") is not False
                or rank.get("source_validation_is_not_buyer_acceptance") is not True
                or executive.get("commercial_authority") != "none"
                or executive.get("external_execution_performed") is not False
                or exec_at < router_at
                or type(rank.get("validated_opportunity_count")) is not int
                or not 0 <= rank["validated_opportunity_count"] <= count
                or rank["validated_opportunity_count"] != executive.get("validated_opportunity_count")):
            raise RuntimeObservationError("astra_ranking_not_verified")
        evidence.append("runtime:astra_sha256_" + digest)
        metric = {"ranking_status": rank["status"],
                  "validated_opportunities": rank["validated_opportunity_count"]}

    elif lane == "founder_radar":
        api = fetch_local("/v1/founder-dashboard/overview")
        if not isinstance(api, Mapping):
            raise RuntimeObservationError("founder_api_missing")
        radar = api.get("opportunity_radar")
        item = radar.get("lifecycle_evidence") if isinstance(radar, Mapping) else None
        if (not isinstance(item, Mapping)
                or item.get("schema_version") != "empire.founder_radar_lifecycle_evidence.v1"
                or item.get("status") != "CURRENT_DERIVED_HISTORY_OBSERVED"
                or item.get("history_verified_for_cycle") is not True
                or item.get("execution_authority") != "none"
                or item.get("commercial_validation_verified") is not False
                or item.get("outreach_authorized") is not False
                or item.get("router_opportunity_count") != count
                or item.get("router_stage_counts") != router.get("stage_counts")
                or _stamp(item.get("router_observed_at")) != router_at
                or item.get("new_identity_count_latest_cycle") != history.get("new_identity_count")
                or item.get("derived_stage_transitions_latest_cycle") != history.get("stage_transition_count_this_cycle")):
            raise RuntimeObservationError("resident_founder_history_not_verified")
        signature = sha256(json.dumps(item, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        evidence.append("verification:founder_http200_sha256_" + signature)
        metric = {"history_verified": True,
                  "observed_opportunities": count}

    else:
        daily, digest = _read(root, "daily_results/latest.json")
        sources["daily"] = digest
        _safe_observe(daily, schema="empire.daily_results.v1")
        _fresh(daily.get("generated_at"), now=clock)
        report = daily.get("opportunity_daily")
        if (not isinstance(report, Mapping)
                or report.get("schema_version") != "empire.daily_results.opportunity_activity.v1"
                or report.get("mode") != "OBSERVE"
                or report.get("execution_authority") != "none"
                or report.get("external_execution_performed") is not False
                or report.get("forecast_as_realized_revenue") is not False
                or report.get("coverage") != "LATEST_COMPLETED_CYCLE_ONLY_NOT_DAILY_TOTAL"):
            raise RuntimeObservationError("daily_activity_not_verified")
        advanced, proved = report.get("advanced"), report.get("proved")
        if (not isinstance(advanced, Mapping)
                or advanced.get("commercial_promotion_verified") is not False
                or not isinstance(proved, Mapping)
                or proved.get("status") != "CANONICAL_OUTCOME_EVENT_FEED_NOT_BOUND"
                or proved.get("verified_commercial_outcomes_today") is not None):
            raise RuntimeObservationError("daily_report_commercial_truth_untrusted")
        api = fetch_local("/v1/founder-daily-results/latest")
        if api != daily:
            raise RuntimeObservationError("resident_daily_api_snapshot_mismatch")
        evidence.append("runtime:daily_sha256_" + digest)
        evidence.append("verification:daily_http200_same_snapshot")
        metric = {"latest_cycle_coverage": report["coverage"],
                  "commercial_outcome_feed_bound": False}

    return {
        "schema_version": SCHEMA,
        "status": "RUNTIME_OBSERVED",
        "task": task,
        "lane": lane,
        "observed_at": clock.isoformat(),
        "evidence_refs": evidence,
        "source_hashes": sources,
        "metrics": metric,
        "checklist_closure_verified": False,
        "independent_customer_revenue_verified": False,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }
