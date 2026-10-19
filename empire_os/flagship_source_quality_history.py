"""Longitudinal custody of real aggregate source-quality observations.

Consumes ONLY existing canonical Source Intelligence mining review. Each
entry is a bounded, locally hash-linked observation; never original data
or an invented historical baseline. A second independent observation at
least 24h later is necessary to compare distributions. Four canonical
sources are NOT a statistically powered or independent training cohort.

Local chain detects accidental corruption; no external tamper-proof
signature, source authentication, or revenue/probability inference.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import fcntl
import json
import os
import stat

from empire_os.flagship_quality_integrations import (
    CATEGORIES, quality_distribution_preflight,
)
from empire_os.revenue_stream_mining import SOURCES, SCHEMA as MINING_SCHEMA

SCHEMA = "empire.flagship_source_quality_history.v1"
GENESIS = "0" * 64
MAX_OBSERVATIONS = 120
MAX_FILE_BYTES = 128_000
MAX_ROW_BYTES = 3200
MIN_COMPARISON = timedelta(hours=24)
MAX_COMPARISON = timedelta(days=30)
PATH = "runtime/scientific_evaluation/flagship_source_quality_history.jsonl"

STATUS_MAP = {
    "FRESH": "OBSERVED",
    "OBSERVED": "OBSERVED",
    "STALE": "STALE",
    "MISSING": "MISSING",
    "INVALID": "HELD",
    "UNTRUSTED": "HELD",
    "FUTURE_HELD": "HELD",
    "UNAVAILABLE": "UNKNOWN",
}
LANE_FOR_SOURCE = {
    "acquisition": "acquisition",
    "opportunity_routes": "public_opportunity",
    "quant": "quant_economics",
    "competitor": "competitor",
}


class SourceQualityCustodyHold(ValueError):
    pass


def _utc(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise SourceQualityCustodyHold("aware quality observation clock required")
    return at.astimezone(timezone.utc)


def _sha(document: Mapping[str, Any]) -> str:
    return sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _stamp(raw: Any) -> datetime:
    if not isinstance(raw, str) or len(raw) > 60:
        raise SourceQualityCustodyHold("invalid quality timestamp")
    try:
        timestamp = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise SourceQualityCustodyHold("malformed quality timestamp") from exc
    return _utc(timestamp)


def from_canonical_stream_review(
    review: Mapping[str, Any], *, as_of: datetime,
) -> dict[str, Any]:
    """Construct a privacy-safe source observation, not an empirical label."""
    now = _utc(as_of)
    if (not isinstance(review, Mapping)
            or review.get("schema_version") != MINING_SCHEMA
            or review.get("mode") != "OBSERVE"
            or review.get("execution_authority") != "none"
            or review.get("worker_dispatched") is not False
            or review.get("commercial_execution_authorized") is not False
            or review.get("source_count") != len(SOURCES)):
        raise SourceQualityCustodyHold("invalid canonical mining review")
    sources = review.get("sources")
    lanes = review.get("department_lanes")
    if (not isinstance(sources, Mapping) or set(sources) != set(SOURCES)
            or not isinstance(lanes, list) or len(lanes) != 5):
        raise SourceQualityCustodyHold("unknown source universe")
    by_lane = {lane.get("stream"): lane for lane in lanes if isinstance(lane, Mapping)}
    if len(by_lane) != len(lanes):
        raise SourceQualityCustodyHold("duplicate source lane")
    distributions = Counter()
    fingerprints = {}
    for name in sorted(SOURCES):
        source = sources[name]
        if not isinstance(source, Mapping) or source.get("status") not in STATUS_MAP:
            raise SourceQualityCustodyHold("unrecognized source quality status")
        status = source["status"]
        if (status not in ("FRESH", "OBSERVED")
                and source.get("aggregate") is not None):
            raise SourceQualityCustodyHold("held source cannot carry trusted aggregate")
        lane = by_lane.get(LANE_FOR_SOURCE[name])
        if (not isinstance(lane, Mapping)
                or lane.get("status") != status
                or lane.get("execution_authority") != "none"):
            raise SourceQualityCustodyHold("source lane mismatch")
        digest = lane.get("evidence_fingerprint")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise SourceQualityCustodyHold("invalid source fingerprint")
        fingerprints[name] = digest
        distributions[STATUS_MAP[status]] += 1
    return {
        "schema_version": "empire.flagship_source_quality.observation.v1",
        "observed_at": now.isoformat(),
        "source_universe": "FOUR_EXISTING_CANONICAL_INTERNAL_SOURCE_ADAPTERS",
        "source_count": len(SOURCES),
        "source_quality_categories": {
            category: distributions[category] for category in CATEGORIES
        },
        "source_evidence_fingerprints": fingerprints,
        "source_rows_or_contacts_exported": False,
        "source_recency_is_not_independent_verification": True,
        "independent_outcomes_sampled": 0,
        "customer_delivery_authorized": False,
        "external_execution_authorized": False,
        "execution_authority": "none",
    }


def _check_observation(value: Any) -> datetime:
    if (not isinstance(value, Mapping)
            or set(value) != {
                "schema_version", "observed_at", "source_universe",
                "source_count", "source_quality_categories",
                "source_evidence_fingerprints", "source_rows_or_contacts_exported",
                "source_recency_is_not_independent_verification",
                "independent_outcomes_sampled", "customer_delivery_authorized",
                "external_execution_authorized", "execution_authority",
            }
            or value.get("schema_version") != "empire.flagship_source_quality.observation.v1"
            or value.get("source_universe")
            != "FOUR_EXISTING_CANONICAL_INTERNAL_SOURCE_ADAPTERS"
            or value.get("source_count") != len(SOURCES)
            or value.get("source_rows_or_contacts_exported") is not False
            or value.get("source_recency_is_not_independent_verification") is not True
            or value.get("independent_outcomes_sampled") != 0
            or value.get("customer_delivery_authorized") is not False
            or value.get("external_execution_authorized") is not False
            or value.get("execution_authority") != "none"):
        raise SourceQualityCustodyHold("invalid observation contract")
    distribution = value.get("source_quality_categories")
    fingerprints = value.get("source_evidence_fingerprints")
    if (not isinstance(distribution, Mapping)
            or set(distribution) != set(CATEGORIES)
            or any(type(n) is not int or n < 0 or n > len(SOURCES)
                   for n in distribution.values())
            or sum(distribution.values()) != len(SOURCES)
            or not isinstance(fingerprints, Mapping)
            or set(fingerprints) != set(SOURCES)
            or any(not isinstance(d, str) or len(d) != 64
                   or any(c not in "0123456789abcdef" for c in d)
                   for d in fingerprints.values())):
        raise SourceQualityCustodyHold("invalid source quality observation counts")
    return _stamp(value.get("observed_at"))


def verify_history(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Validate complete local journal. A truncated window is NOT trusted."""
    if (not isinstance(rows, list) or not 0 <= len(rows) <= MAX_OBSERVATIONS):
        raise SourceQualityCustodyHold("unbounded observation history")
    previous = GENESIS
    seen: set[str] = set()
    old_timestamp = None
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != {
            "sequence", "previous_sha256", "chain_sha256", "observation",
        }:
            raise SourceQualityCustodyHold("invalid history row")
        entry = row["observation"]
        timestamp = _check_observation(entry)
        if (type(row["sequence"]) is not int or row["sequence"] != index
                or row["previous_sha256"] != previous):
            raise SourceQualityCustodyHold("history sequence or chain mismatch")
        expected = _sha({
            "sequence": index, "previous_sha256": previous,
            "observation": entry,
        })
        if row["chain_sha256"] != expected:
            raise SourceQualityCustodyHold("observation chain digest mismatch")
        if old_timestamp is not None and timestamp <= old_timestamp:
            raise SourceQualityCustodyHold("non-monotonic observation clock")
        if entry["observed_at"] in seen:
            raise SourceQualityCustodyHold("duplicate observation time")
        seen.add(entry["observed_at"])
        old_timestamp = timestamp
        previous = expected
    return {
        "verified_local_chain": True,
        "externally_anchored_or_signed": False,
        "observations": len(rows),
        "head_chain_sha256": previous,
    }


def _parse_journal_bytes(data: bytes) -> list[Mapping[str, Any]]:
    if len(data) > MAX_FILE_BYTES:
        raise SourceQualityCustodyHold("observation journal exceeds private limit")
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise SourceQualityCustodyHold("incomplete journal write")
    rows: list[Mapping[str, Any]] = []
    try:
        for line in data.splitlines():
            if not 0 < len(line) <= MAX_ROW_BYTES:
                raise SourceQualityCustodyHold("invalid journal row length")
            rows.append(json.loads(line))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise SourceQualityCustodyHold("journal contains unreadable row") from exc
    verify_history(rows)
    return rows


def read_quality_history(path: Path) -> list[Mapping[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise SourceQualityCustodyHold("unsafe journal path")
    if (path.stat().st_nlink != 1 or
            path.stat().st_mode & 0o077 != 0):
        raise SourceQualityCustodyHold("unsafe journal link count or permissions")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SourceQualityCustodyHold("journal read failed") from exc
    return _parse_journal_bytes(data)


def plan_quality_observation(
    history: list[Mapping[str, Any]], observation: Mapping[str, Any],
) -> dict[str, Any]:
    verify_history(history)
    timestamp = _check_observation(observation)
    if history:
        last = history[-1]["observation"]
        prior = _stamp(last["observed_at"])
        if timestamp < prior:
            raise SourceQualityCustodyHold("backdated observation not allowed")
        if timestamp == prior:
            if observation == last:
                return {"status": "EXACT_OBSERVATION_REPLAY", "written": False,
                        "head_chain_sha256": history[-1]["chain_sha256"]}
            raise SourceQualityCustodyHold("conflicting observation at same clock")
    seq = len(history)
    if seq >= MAX_OBSERVATIONS:
        raise SourceQualityCustodyHold("journal retention cap reached; review required")
    previous = history[-1]["chain_sha256"] if history else GENESIS
    entry = {
        "sequence": seq,
        "previous_sha256": previous,
        "observation": dict(observation),
    }
    entry["chain_sha256"] = _sha(entry)
    if len(json.dumps(entry, separators=(",", ":")).encode()) > MAX_ROW_BYTES:
        raise SourceQualityCustodyHold("bounded journal entry exceeds limit")
    return {"status": "APPEND_READY", "entry": entry, "written": False}


def append_quality_observation(
    path: Path, observation: Mapping[str, Any], *, apply: bool = False,
) -> dict[str, Any]:
    """Explicit local file write; same lock and fsync; never DB/external."""
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise SourceQualityCustodyHold("unsafe journal or directory")
    if not apply:
        history = read_quality_history(path)
        return plan_quality_observation(history, observation)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.parent.is_symlink():
        raise SourceQualityCustodyHold("unsafe journal path after creation")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        current = os.fstat(handle.fileno())
        if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                or current.st_mode & 0o077 != 0):
            raise SourceQualityCustodyHold("unsafe journal file custody")
        history = _parse_journal_bytes(handle.read(MAX_FILE_BYTES + 1))
        planned = plan_quality_observation(history, observation)
        if planned["status"] != "APPEND_READY":
            return planned
        line = json.dumps(planned["entry"], sort_keys=True, separators=(",", ":")).encode() + b"\n"
        if handle.tell() + len(line) > MAX_FILE_BYTES:
            raise SourceQualityCustodyHold("journal physical capacity reached")
        handle.seek(0, os.SEEK_END)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "status": "APPENDED_PRIVATE_SOURCE_QUALITY_OBSERVATION",
        "written": True,
        "observation_sequence": planned["entry"]["sequence"],
        "head_chain_sha256": planned["entry"]["chain_sha256"],
        "external_anchor_verified": False,
        "production_database_writes": False,
        "external_data_exported": False,
    }


def review_quality_history(
    path: Path, *, as_of: datetime,
) -> dict[str, Any]:
    now = _utc(as_of)
    base = {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "NEED_FIRST_CANONICAL_OBSERVATION",
        "observation_count": 0,
        "source_universe": "FOUR_EXISTING_CANONICAL_INTERNAL_SOURCE_ADAPTERS",
        "comparison_status": "NOT_POSSIBLE_WITH_ONE_SOURCE_SNAPSHOT",
        "separation_hours": None,
        "absolute_proportion_changes": None,
        "evidently_drift_test_executed": False,
        "statistical_significance_established": False,
        "source_authenticity_independently_verified": False,
        "buyer_or_revenue_verified": False,
        "model_retrained": False,
        "execution_authority": "none",
    }
    try:
        observations = read_quality_history(path)
    except SourceQualityCustodyHold:
        return dict(base, status="LOCAL_SOURCE_QUALITY_CUSTODY_HELD",
                    comparison_status="CORRUPT_OR_UNTRUSTED_LOCAL_HISTORY")
    if not observations:
        return base
    old = _stamp(observations[0]["observation"]["observed_at"])
    latest = _stamp(observations[-1]["observation"]["observed_at"])
    if latest > now:
        return dict(base, status="LOCAL_SOURCE_QUALITY_CUSTODY_HELD",
                    comparison_status="FUTURE_SOURCE_QUALITY_OBSERVATION")
    latest_counts = observations[-1]["observation"]["source_quality_categories"]
    action = (
        "INVESTIGATE_HELD_SOURCE_EVIDENCE" if latest_counts["HELD"]
        else "CHECK_STALE_SOURCE_REFRESH" if latest_counts["STALE"]
        else "RESTORE_MISSING_SOURCE_ADAPTER" if latest_counts["MISSING"]
        else "REVIEW_UNAVAILABLE_SOURCE_GATEWAY" if latest_counts["UNKNOWN"]
        else "COLLECT_INDEPENDENT_SECOND_OBSERVATION"
    )
    overview = dict(base, status="HISTORICAL_BASELINE_OBSERVED_NOT_CALIBRATED",
                    observation_count=len(observations),
                    latest_quality_category_counts=dict(latest_counts),
                    next_internal_quality_action=action,
                    earliest_observed_at=old.isoformat(),
                    latest_observed_at=latest.isoformat(),
                    local_chain_verified=True,
                    external_anchor_verified=False)
    if len(observations) < 2:
        return overview
    duration = latest - old
    if duration < MIN_COMPARISON or duration > MAX_COMPARISON:
        return dict(overview, comparison_status=(
            "NEED_AT_LEAST_24H_SEPARATION" if duration < MIN_COMPARISON
            else "HISTORICAL_REFERENCE_TOO_OLD"
        ), separation_hours=round(duration.total_seconds()/3600, 2))
    reference = observations[0]["observation"]["source_quality_categories"]
    current = observations[-1]["observation"]["source_quality_categories"]
    comparison = quality_distribution_preflight(reference, current, as_of=now)
    if comparison["absolute_proportion_changes"] is None:
        return dict(overview, comparison_status="INSUFFICIENT_SOURCE_COHORT")
    return dict(
        overview, status="DESCRIPTIVE_SOURCE_QUALITY_CHANGE_REVIEW",
        comparison_status="DESCRIPTIVE_COUNTS_ONLY_FOUR_CORRELATED_ADAPTERS",
        separation_hours=round(duration.total_seconds()/3600, 2),
        absolute_proportion_changes=comparison["absolute_proportion_changes"],
        evidently_drift_test_executed=False,
        statistical_significance_established=False,
        quality_change_does_not_establish_forecast_accuracy=True,
    )
