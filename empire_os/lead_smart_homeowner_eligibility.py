"""Prelaunch ZIP guidance: static public preview, never call authority.

The public site is exported to static HTML. Its coverage preview is a read-only
summary of an independently verified, fresh buyer-provided targeting snapshot.
It is NOT a live Ringba bid, call-routing response, or payable-call guarantee.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


class PreviewEvidenceError(ValueError):
    pass


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PreviewEvidenceError("timestamp missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreviewEvidenceError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise PreviewEvidenceError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _age_ok(value: datetime, now: datetime, seconds: int) -> bool:
    age = (now - value).total_seconds()
    return 0 <= age <= seconds


def make_public_zip_preview(
    snapshot: Mapping[str, Any],
    activation: Mapping[str, Any],
    *,
    snapshot_sha256: str,
    intelligence_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise PreviewEvidenceError("UTC-aware time required")
    now = now.astimezone(timezone.utc)

    if (
        snapshot.get("schema_version") != "empire.lead_smart.coverage_snapshot.v1"
        or snapshot.get("mode") != "OBSERVE"
        or activation.get("schema_version")
        != "empire.lead_smart.zip_targeting_gate.v1"
        or activation.get("mode") != "PREACTIVATION"
        or activation.get("zip_targeting_gate_verified") is not True
        or activation.get("zip_coverage_activation_verified") is not True
        or activation.get("source_fresh_for_targeting") is not True
    ):
        raise PreviewEvidenceError("verified preactivation ZIP snapshot required")
    refs = activation.get("evidence_refs") or {}
    if (
        refs.get("coverage_snapshot") != "sha256:" + snapshot_sha256
        or refs.get("coverage_intelligence") != "sha256:" + intelligence_sha256
        or snapshot.get("source_hash") != activation.get("source_hash")
        or snapshot.get("observed_at") != activation.get("source_observed_at")
    ):
        raise PreviewEvidenceError("ZIP activation evidence does not match source")

    observed_at = _timestamp(snapshot.get("observed_at"))
    source_updated_at = _timestamp(
        (activation.get("verified_freshness") or {}).get(
            "source_newest_last_updated"
        )
    )
    if not (
        _age_ok(observed_at, now, 21600)
        and _age_ok(source_updated_at, now, 108000)
    ):
        raise PreviewEvidenceError("ZIP snapshot expired")

    rows = snapshot.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PreviewEvidenceError("coverage rows missing")
    zips: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise PreviewEvidenceError("invalid coverage row")
        zip_code = row.get("zip")
        if not isinstance(zip_code, str) or re.fullmatch(r"[0-9]{5}", zip_code) is None:
            raise PreviewEvidenceError("invalid ZIP row")
        if zip_code in zips:
            raise PreviewEvidenceError("duplicate ZIP in coverage")
        zips.add(zip_code)
    coverage = snapshot.get("coverage") or {}
    if (
        len(zips) != activation.get("zip_count")
        or len(rows) != coverage.get("row_count")
        or len(zips) != coverage.get("unique_zip_count")
    ):
        raise PreviewEvidenceError("ZIP row counts disagree")

    # A public ZIP preview is a snapshot for initial targeting guidance only.
    # No payout/caller identifiers or configured phone number are exposed.
    expires_at = min(
        now + timedelta(hours=1),
        observed_at + timedelta(hours=6),
        source_updated_at + timedelta(hours=30),
    )
    return {
        "schema_version": "empire.lead_smart.public_zip_preview.v1",
        "mode": "PREACTIVATION",
        "purpose": "COVERAGE_GUIDANCE_ONLY",
        "generated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "covered_zips": sorted(zips),
        "count": len(zips),
        "call_authorized": False,
        "buyer_route_verified": False,
        "execution_authority": "NONE",
        "source": "Lead Smart coverage guidance (not live buyer availability)",
    }


def buyer_hours_preview(*, now: datetime | None = None) -> dict[str, Any]:
    """Local Central Time guidance, never independent authorization.

    Seth used 'CST'; whether his hours follow daylight-saving transitions
    remains to be confirmed. We therefore display an assumed zone and
    explicitly prevent this calculation from granting a call.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise PreviewEvidenceError("timezone-aware time required")
    local = current.astimezone(ZoneInfo("America/Chicago"))
    weekday = local.weekday() < 5
    start, end = (8, 18) if weekday else (10, 16)
    local_minutes = local.hour * 60 + local.minute
    in_window = start * 60 <= local_minutes < end * 60
    return {
        "timezone_assumption": "America/Chicago (DST interpretation unverified)",
        "buyer_hours_reported": "Mon-Fri 08:00-18:00; Sat-Sun 10:00-16:00",
        "local_time": local.isoformat(),
        "within_reported_window": in_window,
        "timezone_interpretation_verified": False,
        "call_authorized": False,
        "execution_authority": "NONE",
    }


def generate_from_files(
    snapshot_path: Path,
    activation_path: Path,
    intelligence_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    snapshot_bytes = snapshot_path.read_bytes()
    intelligence_bytes = intelligence_path.read_bytes()
    return make_public_zip_preview(
        json.loads(snapshot_bytes),
        json.loads(activation_path.read_bytes()),
        snapshot_sha256=hashlib.sha256(snapshot_bytes).hexdigest(),
        intelligence_sha256=hashlib.sha256(intelligence_bytes).hexdigest(),
        now=now,
    )
