"""Bounded, fail-closed read-only Founder Predictive Cloud status endpoint.

Runtime snapshot health is separate from original issuer/customer prediction
proof. An arbitrary JSON file cannot authorize a healthy Cloud dashboard.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter

from empire_os.predictive_cloud_status import COMPONENTS

DEFAULT_SNAPSHOT = Path(
    "/srv/empire_os/runtime/predictive_cloud/status_latest.json"
)
SCHEMA = "empire.predictive_cloud.status.v2"
MAX_SNAPSHOT_BYTES = 200_000
MAX_SNAPSHOT_AGE_SECONDS = 900
MAX_FUTURE_SKEW_SECONDS = 120
PUBLIC_FIELDS = (
    "schema_version", "mode", "generated_at", "component_count",
    "available_component_count", "fresh_component_count",
    "unavailable_components", "stale_components",
    "unknown_freshness_components", "future_untrusted_components",
    "runtime_all_sources_fresh", "framework_operational",
    "customer_forecast_verified",
    "original_terminal_outcomes_authenticated_by_status",
    "original_frozen_forecast_registry_authenticated_by_status",
    "commercial_prediction_authorized", "organization", "components",
    "outreach_sent_by_status", "payment_action_by_status",
    "revenue_recognized_by_status", "execution_authority",
)


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "available": False,
        "mode": "OBSERVE",
        "status": "CLOUD_STATUS_SOURCE_HELD",
        "reason_code": reason,
        "components": {},
        "unavailable_components": [],
        "stale_components": [],
        "unknown_freshness_components": [],
        "future_untrusted_components": [],
        "runtime_all_sources_fresh": False,
        "framework_operational": False,
        "customer_forecast_verified": False,
        "commercial_prediction_authorized": False,
        "execution_authority": "none",
    }


def _trust(value: Mapping[str, Any], now: datetime) -> bool:
    if (value.get("schema_version") != SCHEMA
            or value.get("mode") != "OBSERVE"
            or value.get("execution_authority") != "none"
            or value.get("outreach_sent_by_status") is not False
            or value.get("payment_action_by_status") is not False
            or value.get("revenue_recognized_by_status") is not False
            or value.get("customer_forecast_verified") is not False
            or value.get("commercial_prediction_authorized") is not False
            or value.get("original_terminal_outcomes_authenticated_by_status")
                 is not False
            or value.get("original_frozen_forecast_registry_authenticated_by_status")
                 is not False):
        return False
    try:
        stamp = datetime.fromisoformat(value["generated_at"].replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            return False
        age = (now - stamp.astimezone(timezone.utc)).total_seconds()
        if not -MAX_FUTURE_SKEW_SECONDS <= age <= MAX_SNAPSHOT_AGE_SECONDS:
            return False
    except (KeyError, ValueError, TypeError, AttributeError):
        return False
    rows = value.get("components")
    if not isinstance(rows, dict) or set(rows) != set(COMPONENTS):
        return False
    count = value.get("component_count")
    available = value.get("available_component_count")
    fresh_count = value.get("fresh_component_count")
    if (type(count) is not int or count != len(COMPONENTS)
            or type(available) is not int or not 0 <= available <= count
            or type(fresh_count) is not int or not 0 <= fresh_count <= available):
        return False
    if any(not isinstance(item, Mapping)
           or type(item.get("available")) is not bool
           or item.get("freshness") not in (
               "fresh", "stale", "unknown", "future_untrusted")
           for item in rows.values()):
        return False
    derived = {
        "available_component_count": sum(x["available"] for x in rows.values()),
        "fresh_component_count": sum(x["freshness"] == "fresh" for x in rows.values()),
        "unavailable_components": [
            k for k, x in rows.items() if x["available"] is False
        ],
        "stale_components": [
            k for k, x in rows.items() if x["freshness"] == "stale"
        ],
        "unknown_freshness_components": [
            k for k, x in rows.items()
            if x["available"] and x["freshness"] == "unknown"
        ],
        "future_untrusted_components": [
            k for k, x in rows.items()
            if x["freshness"] == "future_untrusted"
        ],
    }
    for key, expected in derived.items():
        observed = value.get(key)
        if isinstance(expected, list):
            if (not isinstance(observed, list)
                    or len(observed) != len(expected)
                    or not all(type(item) is str for item in observed)
                    or set(observed) != set(expected)):
                return False
        elif observed != expected:
            return False
    for component, item in rows.items():
        freshness = item["freshness"]
        if not item["available"]:
            if (freshness != "unknown" or item.get("observed_at") is not None
                    or item.get("age_seconds") is not None):
                return False
            continue
        observed_text = item.get("observed_at")
        observed_age = item.get("age_seconds")
        if freshness == "unknown":
            if observed_text is not None or observed_age is not None:
                return False
            continue
        if type(observed_text) is not str:
            return False
        try:
            observed_time = datetime.fromisoformat(
                observed_text.replace("Z", "+00:00")
            )
            if observed_time.utcoffset() is None:
                return False
        except (ValueError, TypeError):
            return False
        delta = (stamp - observed_time.astimezone(timezone.utc)).total_seconds()
        age_seconds = max(0, int(delta))
        if freshness == "future_untrusted":
            if delta >= -MAX_FUTURE_SKEW_SECONDS or observed_age is not None:
                return False
        elif (type(observed_age) is not int
              or abs(observed_age - age_seconds) > 1):
            return False
        elif freshness == "fresh":
            if not -MAX_FUTURE_SKEW_SECONDS <= delta <= COMPONENTS[component]["fresh_seconds"]:
                return False
        elif freshness == "stale":
            if delta <= COMPONENTS[component]["fresh_seconds"]:
                return False
    healthy = (fresh_count == count
               and not derived["unavailable_components"]
               and not derived["stale_components"]
               and not derived["unknown_freshness_components"]
               and not derived["future_untrusted_components"])
    if (value.get("runtime_all_sources_fresh") is not healthy
            or value.get("framework_operational") is not healthy):
        return False
    return isinstance(value.get("organization"), dict)


def read_predictive_cloud_status(
    path: Path = DEFAULT_SNAPSHOT, *,
    now: datetime | None = None,
) -> dict[str, Any]:
    try:
        if path.is_symlink():
            return _unavailable("SOURCE_SYMLINK_REFUSED")
        with path.open("rb") as handle:
            raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            return _unavailable("SOURCE_OVERSIZED")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _unavailable("SOURCE_UNAVAILABLE")
    if not isinstance(value, dict):
        return _unavailable("SOURCE_INVALID")
    current = now or datetime.now(timezone.utc)
    if (not isinstance(current, datetime) or current.utcoffset() is None
            or not _trust(value, current.astimezone(timezone.utc))):
        return _unavailable("SOURCE_UNVERIFIED_OR_STALE")
    # Do not echo unexpected JSON fields, credentials or other private source
    # metadata even when a valid envelope is appended with unrelated fields.
    return {"available": True, **{k: value[k] for k in PUBLIC_FIELDS}}


def create_predictive_cloud_status_router(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/predictive-cloud",
        tags=["predictive-cloud"],
    )

    @router.get("/status")
    def status():
        return read_predictive_cloud_status(snapshot_path)

    return router
