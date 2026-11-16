"""Read-only Founder surface for canonical Predictive Cloud status."""
from __future__ import annotations

import json
import math
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response


DEFAULT_SNAPSHOT = Path(
    "/srv/empire_os/runtime/predictive_cloud/status_latest.json"
)
MAX_SNAPSHOT_BYTES = 2_000_000
MAX_SNAPSHOT_AGE_SECONDS = 1800


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "empire.predictive_cloud.status.v2",
        "available": False, "snapshot_state": reason,
        "framework_operational": False, "commercial_prediction_authorized": False,
        "customer_forecast_verified": False, "mode": "OBSERVE", "components": {},
        "unavailable_components": [], "stale_components": [], "execution_authority": "none",
    }


def _reject_nonfinite(value: str) -> None:
    raise ValueError("finite JSON required")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("finite JSON required")
    return number


def read_predictive_cloud_status(
    path: Path = DEFAULT_SNAPSHOT,
    *, now: datetime | None = None,
) -> dict[str, Any]:
    """Read bounded status metadata; presence never authenticates its evidence."""
    try:
        if path.resolve() != path.absolute():
            return _unavailable("UNTRUSTED_SNAPSHOT_PATH")
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SNAPSHOT_BYTES:
                return _unavailable("INVALID_SNAPSHOT_SIZE_OR_TYPE")
            with os.fdopen(os.dup(fd), "rb") as stream:
                raw = stream.read(MAX_SNAPSHOT_BYTES + 1)
            if len(raw) > MAX_SNAPSHOT_BYTES:
                return _unavailable("INVALID_SNAPSHOT_SIZE_OR_TYPE")
        finally:
            os.close(fd)
        value = json.loads(raw, parse_constant=_reject_nonfinite, parse_float=_finite_float)
        if (not isinstance(value, dict)
                or value.get("schema_version") not in (
                    "empire.predictive_cloud.status.v1", "empire.predictive_cloud.status.v2")
                or value.get("mode") != "OBSERVE"
                or value.get("execution_authority") != "none"
                or not isinstance(value.get("components"), dict)):
            return _unavailable("INVALID_SNAPSHOT_CONTRACT")
        # v1 had no mandatory generation clock; retain that interface but
        # explicitly identify its unknown freshness. Current v2 must be fresh.
        freshness = "UNKNOWN_LEGACY_SNAPSHOT_AGE"
        if value.get("generated_at") is not None or value["schema_version"].endswith(".v2"):
            generated = datetime.fromisoformat(value["generated_at"].replace("Z", "+00:00"))
            clock = now or datetime.now(timezone.utc)
            if generated.utcoffset() is None or clock.utcoffset() is None:
                return _unavailable("INVALID_SNAPSHOT_CLOCK")
            age = (clock.astimezone(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds()
            if not 0 <= age <= MAX_SNAPSHOT_AGE_SECONDS:
                return _unavailable("STALE_OR_FUTURE_SNAPSHOT")
            freshness = "FRESH_STATUS_SNAPSHOT_NOT_SOURCE_ATTESTATION"
        return {**value, "available": True, "snapshot_state": freshness}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return _unavailable("SNAPSHOT_UNAVAILABLE_OR_INVALID")


def create_predictive_cloud_status_router(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/predictive-cloud",
        tags=["predictive-cloud"],
    )

    @router.get("/status")
    def status(response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return read_predictive_cloud_status(snapshot_path)

    return router
