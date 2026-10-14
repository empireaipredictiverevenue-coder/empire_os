"""Read-only YouTube Growth Command Centre projection.

Use only explicitly authenticated, correctly bound owner Analytics responses.
Demographics are aggregate *viewer percentages*, never individuals or inferred
counts; withheld fields stay unavailable, never become 0 or guessed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import os
import stat
from pathlib import Path
from typing import Any, Mapping
import json

from empire_os.media_youtube_channel_binding import (
    EMPIRE_AI_YOUTUBE_CHANNEL_ID, EMPIRE_AI_YOUTUBE_HANDLE_URL,
)

ANALYTICS_PRIVATE_DIR = Path("runtime/media_os/youtube_private_analytics")
SNAPSHOT_PATH = ANALYTICS_PRIVATE_DIR / "youtube_growth_analytics_latest.json"
REFRESH_LOCK_PATH = ANALYTICS_PRIVATE_DIR / ".youtube_growth_analytics_refresh.lock"
SCHEMA = "empire.media.youtube_growth_command_centre.v1"
METRIC_FIELDS = (
    "views", "engagedViews", "estimatedMinutesWatched", "averageViewDuration",
    "subscribersGained", "subscribersLost",
)
# Supported official YouTube Analytics dimensions/metric combinations.
REPORT_SPECS = {
    "overview": (None, "views,engagedViews,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost"),
    "by_day": ("day", "views,estimatedMinutesWatched,subscribersGained,subscribersLost"),
    "age": ("ageGroup", "viewerPercentage"),
    "gender": ("gender", "viewerPercentage"),
    "geography": ("country", "views,estimatedMinutesWatched"),
    "devices": ("deviceType", "views,estimatedMinutesWatched"),
    "traffic": ("insightTrafficSourceType", "views,estimatedMinutesWatched"),
    "content_type": ("creatorContentType", "views,estimatedMinutesWatched"),
}
CATEGORIES = {
    "age": {"age13-17", "age18-24", "age25-34", "age35-44", "age45-54",
            "age55-64", "age65-"},
    "gender": {"male", "female", "user_specified"},
}


def _number(x: Any) -> float | None:
    if x is None:
        return None
    if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
        raise ValueError("youtube_metric_invalid")
    return round(float(x), 4)


def _read_report(payload: Mapping[str, Any], dimensions: tuple[str, ...], metrics: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("youtube_report_invalid")
    columns = payload.get("columnHeaders")
    rows = payload.get("rows", [])
    expected = [*dimensions, *metrics]
    if not isinstance(columns, list) or [c.get("name") for c in columns if isinstance(c, Mapping)] != expected or len(columns) != len(expected):
        raise ValueError("youtube_report_columns_mismatch")
    if not isinstance(rows, list) or len(rows) > 5000:
        raise ValueError("youtube_report_rows_invalid")
    output = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(expected):
            raise ValueError("youtube_report_row_shape_mismatch")
        record = dict(zip(expected, row))
        for key in metrics:
            record[key] = _number(record[key])
        for key in dimensions:
            if not isinstance(record[key], str) or not record[key].strip():
                raise ValueError("youtube_report_dimension_invalid")
        output.append(record)
    return output


def _summary_of(report_rows: list[dict[str, Any]]) -> dict[str, float | None]:
    if not report_rows:
        return {name: None for name in METRIC_FIELDS}
    return {name: report_rows[0].get(name) for name in METRIC_FIELDS}


def project_youtube_growth_metrics(
    *, reports: Mapping[str, Mapping[str, Any]] | None,
    channel_id: str,
    owner_verified: bool,
    analytics_scopes_verified: bool,
    start_date: str,
    end_date: str,
    observed_at: str | None = None,
    report_failures: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if channel_id != EMPIRE_AI_YOUTUBE_CHANNEL_ID:
        raise ValueError("youtube_analytics_channel_identity_mismatch")
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start or (end-start).days > 365:
        raise ValueError("youtube_analytics_window_invalid")
    if reports and (owner_verified is not True or analytics_scopes_verified is not True):
        raise ValueError("unverified_youtube_analytics_cannot_be_presented_as_owned")
    provided = reports or {}
    unrecognised = set(provided)-set(REPORT_SPECS)
    if unrecognised:
        raise ValueError("unexpected_youtube_report")
    datasets: dict[str, dict[str, Any]] = {}
    failures = dict(report_failures or {})
    for key, (dimension, metric_spec) in REPORT_SPECS.items():
        dimensions = tuple([dimension] if dimension else [])
        metrics = tuple(metric_spec.split(","))
        if key not in provided:
            datasets[key] = {
                "status": "UNAVAILABLE",
                "reason": failures.get(key, "not_authenticated_or_not_collected"),
                "rows": None,
                "no_data_inferred": True,
            }
            continue
        rows = _read_report(provided[key], dimensions, metrics)
        if not rows:
            datasets[key] = {
                "status": "WITHHELD_OR_NO_DATA",
                "reason": "youtube_returned_no_rows_or_privacy_threshold",
                "rows": None,
                "no_data_inferred": True,
            }
            continue
        if key in CATEGORIES:
            for row in rows:
                category = row[dimension]
                if category not in CATEGORIES[key]:
                    raise ValueError("youtube_analytics_demographic_category_unknown")
                if row["viewerPercentage"] is None or row["viewerPercentage"] > 100:
                    raise ValueError("youtube_demographic_percentage_invalid")
            # Values may not sum to 100 because YouTube suppresses data.
            # Never correct or fill missing groups, nor infer population.
        datasets[key] = {"status": "OBSERVED", "rows": rows, "reason": None,
                         "no_data_inferred": False}
    overview = datasets["overview"]
    totals = _summary_of(overview["rows"]) if overview["status"] == "OBSERVED" else _summary_of([])
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "handle_url": EMPIRE_AI_YOUTUBE_HANDLE_URL,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "observed_at": observed_at,
        "source": "youtube_analytics_api" if reports else "NOT_CONNECTED",
        "owned_analytics_authenticated": bool(owner_verified and analytics_scopes_verified and reports),
        "overview": totals,
        "reports": datasets,
        "age_and_gender_are_percentage_of_available_viewers_not_people": True,
        "demographic_categories_not_reconstructed": True,
        "niche_demographics_not_inferred_from_video_topics": True,
        "verified_website_traffic": None,
        "verified_commercial_enquiries": None,
        "recognized_revenue_gbp": None,
        "automatic_upload_authorized": False,
        "channel_creation_authorized": False,
        "execution_authority": "none",
    }


def _analytics_unknown(*, now: datetime, reason: str) -> dict[str, Any]:
    end = now.date()
    packet = project_youtube_growth_metrics(
        reports=None, channel_id=EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        owner_verified=False, analytics_scopes_verified=False,
        start_date=(end-timedelta(days=27)).isoformat(),
        end_date=end.isoformat(),
    )
    packet["snapshot_status"] = reason
    return packet


def load_youtube_growth_snapshot(
    repo_root: Path, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only owner aggregate. Missing or stale source stays UNKNOWN."""
    clock = now if now is not None else datetime.now(timezone.utc)
    if (not isinstance(clock, datetime) or clock.tzinfo is None
            or clock.utcoffset() is None):
        raise ValueError("youtube_snapshot_aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    if not isinstance(repo_root, Path) or not repo_root.is_absolute():
        raise ValueError("youtube_snapshot_absolute_root_required")
    path = repo_root / SNAPSHOT_PATH
    private_dir = repo_root / ANALYTICS_PRIVATE_DIR
    if (repo_root.is_symlink() or (repo_root / "runtime").is_symlink()
            or (repo_root / "runtime/media_os").is_symlink()
            or private_dir.is_symlink()):
        return _analytics_unknown(now=clock, reason="UNSAFE_PRIVATE_STORE")
    if private_dir.exists() and (not private_dir.is_dir() or private_dir.stat().st_mode & 0o077):
        return _analytics_unknown(now=clock, reason="UNSAFE_PRIVATE_STORE")
    if path.is_symlink():
        return _analytics_unknown(now=clock, reason="NOT_CONNECTED")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return _analytics_unknown(now=clock, reason="NOT_CONNECTED")
    except OSError:
        raise ValueError("youtube_snapshot_file_open_failed") from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or not 0 < info.st_size <= 2_000_000):
            raise ValueError("youtube_snapshot_private_file_invalid")
        age = clock.timestamp() - info.st_mtime
        if age > 26 * 3600 or age < -300:
            return _analytics_unknown(now=clock, reason="STALE_OR_FUTURE")
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            try:
                data = json.load(stream)
            except (ValueError, UnicodeError):
                raise ValueError("youtube_snapshot_json_invalid") from None
    finally:
        if fd >= 0:
            os.close(fd)
    return validate_youtube_growth_snapshot_packet(data, now=clock)


def validate_youtube_growth_snapshot_packet(data: Any, *, now: datetime) -> dict[str, Any]:
    """Revalidate aggregate-only source rows before display or private persistence."""
    clock = now.astimezone(timezone.utc)
    if not isinstance(data, Mapping) or data.get("schema_version") != SCHEMA or data.get("channel_id") != EMPIRE_AI_YOUTUBE_CHANNEL_ID:
        raise ValueError("youtube_snapshot_contract_mismatch")
    expected=set(_analytics_unknown(now=clock, reason="NOT_CONNECTED"))
    expected.remove("snapshot_status")
    if set(data) != expected:
        raise ValueError("youtube_snapshot_unexpected_fields")
    if (data.get("automatic_upload_authorized") is not False
        or data.get("channel_creation_authorized") is not False
        or data.get("execution_authority") != "none"
        or data.get("mode") != "OBSERVE"
        or data.get("owned_analytics_authenticated") is not True
        or data.get("source") != "youtube_analytics_api"
        or data.get("recognized_revenue_gbp") is not None
        or data.get("verified_commercial_enquiries") is not None
        or data.get("verified_website_traffic") is not None):
        raise ValueError("youtube_snapshot_authority_corrupted")
    period=data.get("date_range")
    if not isinstance(period,Mapping) or set(period)!={"start","end"}:
        raise ValueError("youtube_snapshot_period_invalid")
    try:
        start=date.fromisoformat(period["start"])
        end=date.fromisoformat(period["end"])
    except (ValueError,TypeError,KeyError):
        raise ValueError("youtube_snapshot_period_invalid") from None
    if (start>end or (end-start).days>365 or end>clock.date()+timedelta(days=1)):
        raise ValueError("youtube_snapshot_period_invalid")
    if (data.get("age_and_gender_are_percentage_of_available_viewers_not_people") is not True
        or data.get("demographic_categories_not_reconstructed") is not True
        or data.get("niche_demographics_not_inferred_from_video_topics") is not True):
        raise ValueError("youtube_snapshot_demographic_truth_flags_invalid")
    observed=data.get("observed_at")
    try:
        timestamp=datetime.fromisoformat(observed.replace("Z","+00:00"))
    except (ValueError,AttributeError,TypeError):
        raise ValueError("youtube_snapshot_observed_at_invalid") from None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("youtube_snapshot_observed_at_invalid")
    lag=clock-timestamp.astimezone(timezone.utc)
    if lag>timedelta(hours=26) or lag<timedelta(minutes=-5):
        return _analytics_unknown(now=clock, reason="STALE_OR_FUTURE")
    sections=data.get("reports")
    if not isinstance(sections,Mapping) or set(sections)!=set(REPORT_SPECS):
        raise ValueError("youtube_snapshot_report_contract_invalid")
    for name,(dimension,spec) in REPORT_SPECS.items():
        section=sections[name]
        if not isinstance(section,Mapping) or set(section)!={
            "status","reason","rows","no_data_inferred"
        }:
            raise ValueError("youtube_snapshot_report_contract_invalid")
        if section["status"]=="OBSERVED":
            if (section["reason"] is not None
                    or section["no_data_inferred"] is not False
                    or not isinstance(section["rows"],list) or not section["rows"]):
                raise ValueError("youtube_snapshot_observation_invalid")
            fields=([dimension] if dimension else [])+spec.split(",")
            if any(not isinstance(row,Mapping) or set(row)!=set(fields)
                   for row in section["rows"]):
                raise ValueError("youtube_snapshot_row_fields_invalid")
            verified_rows=_read_report(
                {"columnHeaders":[{"name":key} for key in fields],
                 "rows":[[row[key] for key in fields] for row in section["rows"]]},
                tuple([dimension] if dimension else ()),tuple(spec.split(",")),
            )
            if verified_rows != section["rows"]:
                raise ValueError("youtube_snapshot_row_metric_tampered")
            if name in CATEGORIES and any(
                row[dimension] not in CATEGORIES[name]
                or row["viewerPercentage"] is None
                or row["viewerPercentage"] > 100
                for row in verified_rows
            ):
                raise ValueError("youtube_snapshot_demographic_invalid")
        elif section["status"] not in ("UNAVAILABLE","WITHHELD_OR_NO_DATA") or (
            section["rows"] is not None or section["no_data_inferred"] is not True
            or not isinstance(section["reason"],str)
        ):
            raise ValueError("youtube_snapshot_unavailable_invalid")
    summary=(
        _summary_of(sections["overview"]["rows"])
        if sections["overview"]["status"]=="OBSERVED"
        else _summary_of([])
    )
    if data.get("overview")!=summary:
        raise ValueError("youtube_snapshot_overview_mismatch")
    packet=dict(data)
    packet["snapshot_status"]="CURRENT_PRIVATE_AGGREGATE_NOT_LIVE_OWNER_PROOF"
    return packet
