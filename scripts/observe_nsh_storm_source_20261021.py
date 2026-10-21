"""One-shot, source-grounded OBSERVE use of EXISTING EmpireOS Storm Intelligence.

Never instantiate StormPredictor/StormService or start their poller: those legacy
instances can dispatch Discord/Telegram/callbacks. All work is deterministic
NWS source retrieval -> existing canonical adapters -> existing snapshot builder.

By default this script only prints a restricted status; an explicit stage-only
path can write an OBSERVE snapshot outside the production EmpireOS runtime.
No CRM/DB, canonical production writes, scheduler, outbound, or transactions.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.storm_intelligence_runtime import (
    build_storm_intelligence_runtime,
    write_storm_opportunity_snapshot,
)
from empire_os.storm_predictor import ROOF_DAMAGING_EVENTS, StormEvent, StormPredictor
from empire_os.storm_service import StormService

NWS_URL = "https://api.weather.gov/alerts/active?status=actual"
AGENT = "NationalStormHub/0.2 (https://nationalstormhub.com)"
STAGING_ROOT = Path("/home/ubuntu/empire_releases/national_storm_hub/observations")
MAX_NWS_BYTES = 9 * 1024 * 1024
MAX_SOURCE_ITEMS = 1500
MAX_QUALIFIED_EVENTS = 100


def fetch_current_nws(*, urlopen=urllib.request.urlopen) -> dict[str, Any]:
    req = urllib.request.Request(
        NWS_URL,
        headers={"User-Agent": AGENT, "Accept": "application/geo+json"},
    )
    with urlopen(req, timeout=18) as response:
        if getattr(response, "status", None) != 200:
            raise ValueError("upstream_status_not_ok")
        body = response.read(MAX_NWS_BYTES + 1)
        if len(body) > MAX_NWS_BYTES:
            raise ValueError("nws_payload_limit")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("nws_payload_invalid") from exc
    return result


def canonical_rows_from_payload(
    data: Mapping[str, Any], *,
    checked_at: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    """Project actual NWS warnings only through canonical EmpireOS adapters."""
    if not isinstance(data, Mapping) or data.get("type") != "FeatureCollection":
        raise ValueError("nws_collection_invalid")
    features = data.get("features")
    if not isinstance(features, list) or len(features) > MAX_SOURCE_ITEMS:
        raise ValueError("nws_features_unbounded_or_missing")
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise ValueError("source_clock_invalid")

    retained: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []
    eligible = 0

    for index, item in enumerate(features):
        props = item.get("properties") if isinstance(item, dict) else None
        if not isinstance(props, dict):
            # Invalid unrelated source items do not become qualifying warnings.
            continue
        kind = props.get("event")
        if kind not in ROOF_DAMAGING_EVENTS:
            continue
        eligible += 1
        if eligible > MAX_QUALIFIED_EVENTS:
            raise ValueError("eligible_event_batch_limit")
        if (not isinstance(item.get("id"), str)
            or not isinstance(props.get("sent"), str)):
            rejected.append({"index": str(index), "reason": "source_identity_missing"})
            continue
        try:
            event = StormEvent(
                event_id=item["id"],
                event_type=kind,
                area_description=props.get("areaDesc") or "",
                headline=props.get("headline") or "",
                severity=StormPredictor._severity(None, props),
                occurred_at=props["sent"],
                expires_at=props.get("expires") or "",
                raw={**props, "geometry": item.get("geometry")},
                retrieved_at=checked_at.isoformat(),
            )
            row = StormService._canonical_event_row(event)
            if row["event_id"] in retained:
                # Duplicate source identity must not create two observations.
                if row["event_truth_evidence"]["raw_evidence_hash"] != retained[row["event_id"]]["event_truth_evidence"]["raw_evidence_hash"]:
                    raise ValueError("conflicting_source_evidence")
                continue
            retained[row["event_id"]] = row
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            rejected.append({"index": str(index), "reason":
                str(exc) if str(exc).startswith("source_") else "source_record_invalid"})

    return sorted(retained.values(), key=lambda r: r["event_id"]), rejected[:100], eligible


def observe(
    data: Mapping[str, Any], *,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows, rejected, eligible = canonical_rows_from_payload(data, checked_at=now)
    snapshot = build_storm_intelligence_runtime(
        events=rows, source_rejections=rejected, subjects=(), matches=(),
        readiness=(), now=now,
    )
    if (snapshot["mode"] != "OBSERVE" or
        snapshot["execution_authority"] != "none" or
        snapshot["commercial_authority"] != "none" or
        snapshot["payment_authority"] != "none" or
        snapshot["candidate_count"] != 0 or snapshot["candidates"] != [] or
        snapshot.get("damage_inferred") is not False or
        snapshot.get("buyer_intent_inferred") is not False):
        raise ValueError("observe_authority_invariant")
    status = {
        "mode": "OBSERVE",
        "source": "api.weather.gov/alerts/active?status=actual",
        "analysis_at": now.isoformat(),
        "source_alerts_seen": len(data["features"]),
        "tracked_warning_types_eligible": eligible,
        "source_events_valid": snapshot["diagnostics"]["events_valid"],
        "source_events_rejected": len(rejected) + snapshot["diagnostics"]["events_rejected"],
        "candidate_count": 0,
        "damage_verified": False,
        "buyer_intent_verified": False,
        "revenue_verified": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
        "production_snapshot_changed": False,
    }
    return status, snapshot


def stage_snapshot(root: Path, snapshot: Mapping[str, Any]) -> Path:
    """Stage ONLY under dedicated protected candidate release path."""
    root = Path(root).resolve()
    if not root.is_relative_to(STAGING_ROOT):
        raise ValueError("only_dedicated_observation_staging_allowed")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return write_storm_opportunity_snapshot(root, snapshot)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fetch-live", action="store_true")
    source.add_argument("--source-file", type=Path)
    parser.add_argument("--stage-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.stage_dir and not args.fetch_live:
            raise ValueError("live_source_required_for_stage")
        data = fetch_current_nws() if args.fetch_live else json.loads(args.source_file.read_text())
        source_checked_at = datetime.now(timezone.utc)
        status, snapshot = observe(data, now=source_checked_at)
        status["ingest_mode"] = "LIVE_NWS_FETCH" if args.fetch_live else "SUPPLIED_FILE_REPLAY"
        status["source_fetched_at"] = source_checked_at.isoformat() if args.fetch_live else None
        status["nws_feed_updated_at"] = data.get("updated") if isinstance(data.get("updated"),str) else None
        if args.stage_dir:
            path = stage_snapshot(args.stage_dir, snapshot)
            status["stage_only"] = True
            status["staging_relative_file"] = str(path.relative_to(STAGING_ROOT))
        print(json.dumps(status, sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError, KeyError, urllib.error.URLError) as exc:
        print(json.dumps({
            "status": "SOURCE_OR_CANONICAL_REVIEW_FAILED",
            "reason": str(exc) if str(exc) in {
                "nws_collection_invalid", "nws_features_unbounded_or_missing",
                "eligible_event_batch_limit", "live_source_required_for_stage", "observe_authority_invariant",
                "nws_payload_limit", "nws_payload_invalid",
                "only_dedicated_observation_staging_allowed",
            } else "source_or_provenance_failure",
            "production_snapshot_changed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
