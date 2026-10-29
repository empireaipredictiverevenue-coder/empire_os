"""Bounded read-only Founder Radar compatibility patch for the existing pinned V4.9 app.

This candidate deliberately does NOT alter systemd, credentials, original
routes or the pinned application package. Release requires the original
privileged publisher and explicit independent production validation.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

from fastapi import Request
from starlette.responses import Response, StreamingResponse

PINNED_V49 = Path("/home/ubuntu/empire_releases/predictive_cloud_v49_readonly_20261025")
CANONICAL_ROOT = Path("/srv/empire_os")
ROUTE = "/v1/founder-dashboard/overview"
MAX_JSON_BODY = 2_000_000
MAX_SOURCE_AGE = timedelta(hours=6)

if not PINNED_V49.is_dir() or not CANONICAL_ROOT.is_dir():
    raise RuntimeError("PINNED_FOUNDER_APP_OR_CANONICAL_ROOT_MISSING")
sys.path.insert(0, str(PINNED_V49))
from predictive_cloud_v49_existing_api_overlay_20261025 import app
from empire_os.founder_dashboard import _opportunity_radar_runtime, _read_json


def _verified_radar():
    runtime = CANONICAL_ROOT / "runtime"
    loop = runtime / "opportunity_radar/loop_latest.json"
    intake = runtime / "opportunity_factory/intake_latest.json"
    routes = runtime / "opportunity_factory/evidence_routes_latest.json"
    sources = (loop, intake, routes)
    if any(p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_JSON_BODY for p in sources):
        raise ValueError("unbounded_or_unavailable_canonical_source")
    loop_data = _read_json(loop)
    router_data = _read_json(routes)
    if not isinstance(loop_data, dict) or not isinstance(router_data, dict):
        raise ValueError("missing_canonical_radar_sources")
    now = datetime.now(timezone.utc)
    for stamp in (loop_data.get("finished_at"), router_data.get("generated_at")):
        if not isinstance(stamp, str):
            raise ValueError("missing_radar_source_timestamp")
        value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive_radar_source_timestamp")
        age = now - value.astimezone(timezone.utc)
        if age > MAX_SOURCE_AGE or age < -timedelta(minutes=2):
            raise ValueError("stale_or_future_radar_source")
    radar = _opportunity_radar_runtime(
        loop_data, loop, _read_json(intake), intake, router_data,
    )
    lifecycle = radar.get("lifecycle_evidence")
    if (radar.get("available") is not True
            or radar.get("mode") != "OBSERVE"
            or radar.get("execution_authority") != "none"
            or radar.get("automatic_external_execution_allowed") is not False
            or not isinstance(lifecycle, dict)
            or lifecycle.get("status") != "CURRENT_DERIVED_HISTORY_OBSERVED"
            or lifecycle.get("history_verified_for_cycle") is not True
            or lifecycle.get("execution_authority") != "none"
            or lifecycle.get("commercial_validation_verified") is not False
            or lifecycle.get("outreach_authorized") is not False):
        raise ValueError("canonical_radar_readiness_not_verified")
    return radar


@app.middleware("http")
async def add_verified_radar_history(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != ROUTE or request.method != "GET" or response.status_code != 200:
        return response
    if (not response.headers.get("content-type", "").startswith("application/json")
            or response.headers.get("content-encoding")):
        return response

    # This existing local dashboard route is read-only. Never buffer a large
    # upstream response; stream it unchanged if it exceeds the bounded cap.
    headers = {
        k: v for k, v in response.headers.items()
        if k.lower() not in {"content-length", "transfer-encoding", "content-encoding"}
    }
    raw = bytearray()
    iterator = response.body_iterator
    async for chunk in iterator:
        raw.extend(chunk)
        if len(raw) > MAX_JSON_BODY:
            async def unchanged_stream():
                yield bytes(raw)
                async for remaining in iterator:
                    yield remaining
            return StreamingResponse(
                unchanged_stream(), status_code=response.status_code,
                headers=headers, media_type="application/json",
                background=response.background,
            )
    raw = bytes(raw)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("opportunity_radar"), dict):
            raise ValueError("original_dashboard_not_object")
        data["opportunity_radar"] = _verified_radar()
        modified = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return Response(content=modified, status_code=response.status_code,
                        headers=headers, media_type="application/json")
    except (OSError, TypeError, ValueError, KeyError):
        # Fail closed: do not fabricate verified lifecycle truth.
        return Response(content=raw, status_code=response.status_code,
                        headers=headers, media_type="application/json")
