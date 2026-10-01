"""OBSERVE-only temporal validity and independently evidenced commercial context.

All windows are [start, end). Components carry their own refs and current
validity (source_expires_at and/or freshness_window_seconds). Component scope
is bound to the enclosing opportunity; explicit scope disagreements fail closed.
Nothing here transports factors into ERV or grants commercial authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Mapping


HARD_WINDOW_FIELDS = ("source_expires_at",)


def _parse_time(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, (str, datetime)):
        raise ValueError(f"{field} must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _identity(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _refs(row: Mapping[str, Any]) -> tuple[str, ...]:
    raw = row.get("evidence_refs")
    if not isinstance(raw, (list, tuple)) or not raw or not all(_identity(v) for v in raw):
        return ()
    return tuple(dict.fromkeys(raw))


def _validity(row: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    observed = _parse_time(row.get("observed_at"), "observed_at")
    revalidated = _parse_time(row.get("revalidated_at"), "revalidated_at")
    last = revalidated or observed
    if any(t is not None and t > now for t in (observed, revalidated)):
        raise ValueError("future_validation_timestamp")
    if observed and revalidated and revalidated < observed:
        raise ValueError("revalidation_precedes_observation")
    expiry = _parse_time(row.get("source_expires_at"), "source_expires_at")
    freshness = row.get("freshness_window_seconds")
    if freshness is not None and (type(freshness) is not int or freshness <= 0):
        raise ValueError("freshness_window_seconds must be a positive integer")
    blockers = []
    if not _refs(row):
        blockers.append("evidence_refs_missing")
    if expiry is None and freshness is None:
        blockers.append("temporal_validity_contract_missing")
    if freshness is not None and last is None:
        blockers.append("validation_timestamp_missing")
    expired = ("source_expires_at",) if expiry is not None and expiry <= now else ()
    stale = None
    if freshness is not None and last is not None:
        threshold = last + timedelta(seconds=freshness)
        if threshold <= now:
            stale = int((now - threshold).total_seconds())
    state = "UNKNOWN" if blockers else "EXPIRED" if expired else "STALE" if stale is not None else "ACTIVE"
    return dict(state=state, last_validated_at=last.isoformat() if last else None,
                expired_fields=expired, stale_by_seconds=stale, blockers=tuple(blockers))


def _unknown(reason: str) -> dict[str, Any]:
    return {"state": "UNKNOWN", "blockers": (reason,)}


def _window(row: Mapping[str, Any], prefix: str, now: datetime):
    start = _parse_time(row.get(f"{prefix}_from"), f"{prefix}_from")
    end = _parse_time(row.get(f"{prefix}_until"), f"{prefix}_until")
    if start is None or end is None:
        raise ValueError(f"{prefix}_window_missing")
    if start >= end:
        raise ValueError(f"{prefix}_window_invalid")
    state = "CLOSED" if now >= end else "FUTURE" if now < start else "OPEN"
    return start, end, state


def _component(name: str, raw: Any, parent: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    if raw is None:
        return _unknown("component_missing")
    try:
        if not isinstance(raw, Mapping):
            raise ValueError("component_must_be_mapping")
        for scope in ("opportunity_key", "buyer_key", "offer_key", "market_key"):
            if scope in raw and not _identity(raw[scope]):
                raise ValueError(f"{scope}_invalid")
            if scope in raw and scope in parent and raw[scope] != parent[scope]:
                raise ValueError(f"{scope}_mismatch")
        validity = _validity(raw, now)
        if validity["state"] != "ACTIVE":
            raise ValueError("component_evidence_not_current")
        result = {"state": "KNOWN", "evidence_refs": _refs(raw), "validity": validity,
                  "opportunity_key": parent["opportunity_key"]}
        for scope in ("buyer_key", "offer_key", "market_key"):
            if scope in raw:
                result[scope] = raw[scope]
        if name == "commercial_value":
            ratio = raw.get("retained_value_ratio")
            if type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio <= 1:
                raise ValueError("retained_value_ratio_invalid")
            if raw.get("basis") not in ("explicit_commercial_terms", "validated_calibration") or not _identity(raw.get("basis_ref")):
                raise ValueError("commercial_basis_missing")
            start, end, state = _window(raw, "effective", now)
            if state != "OPEN":
                raise ValueError("outside_effective_interval")
            result.update(retained_value_ratio=ratio, basis=raw["basis"], basis_ref=raw["basis_ref"],
                          effective_from=start.isoformat(), effective_until=end.isoformat())
        elif name == "buyer_timing":
            for scope in ("buyer_key", "offer_key"):
                if not _identity(raw.get(scope)):
                    raise ValueError(f"{scope}_missing")
                result[scope] = raw[scope]
            windows = {}
            for prefix in ("need", "capacity"):
                try:
                    start, end, state = _window(raw, prefix, now)
                    windows[prefix] = (start, end)
                    result[prefix] = {"state": state, "from": start.isoformat(), "until": end.isoformat()}
                except ValueError as exc:
                    result[prefix] = _unknown(str(exc))
            capacity = raw.get("available_capacity")
            if capacity is None:
                result["capacity_availability"] = "UNKNOWN"
            elif type(capacity) not in (int, float) or not math.isfinite(capacity) or capacity < 0:
                raise ValueError("available_capacity_invalid")
            else:
                result["capacity_availability"] = "FULL" if capacity == 0 else "AVAILABLE"
                result["available_capacity"] = capacity
            overlap = "UNKNOWN"
            if len(windows) == 2:
                start = max(w[0] for w in windows.values())
                end = min(w[1] for w in windows.values())
                overlap = "NONE" if start >= end or now >= end else "FUTURE" if now < start else "OPEN"
            result["overlap"] = overlap
            if len(windows) != 2:
                result["state"] = "UNKNOWN"
                result["blockers"] = ("buyer_window_invalid_or_missing",)
        else:
            for scope in ("market_key", "offer_key", "sample_definition"):
                if not _identity(raw.get(scope)):
                    raise ValueError(f"{scope}_missing")
                result[scope] = raw[scope]
            contested, total = raw.get("contested_count"), raw.get("sample_size")
            if type(contested) is not int or type(total) is not int or total <= 0 or not 0 <= contested <= total:
                raise ValueError("competitive_sample_invalid")
            result.update(contested_count=contested, sample_size=total,
                          observed_contested_fraction=contested / total,
                          saturation_penalty=None, market_share_inferred=False)
        return result
    except (ValueError, TypeError, OverflowError) as exc:
        return _unknown(str(exc))


@dataclass(frozen=True)
class OpportunityDecayAssessment:
    opportunity_key: str
    state: str
    as_of: str
    last_validated_at: str | None
    expired_fields: tuple[str, ...]
    stale_by_seconds: int | None
    recency_factor_candidate: float | None
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    commercial_value: dict[str, Any]
    buyer_timing: dict[str, Any]
    competitive_saturation: dict[str, Any]
    recommendation_only: bool = True
    prediction_only: bool = True
    actual_revenue: bool = False
    buyer_intent_inferred: bool = False
    allocation_authorized: bool = False
    outreach_authorized: bool = False
    payment_authorized: bool = False
    execution_authority: str = "none"
    revenue_recognition_authority: str = "none"
    erv_transport_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_opportunity_decay(
    evidence: Mapping[str, Any] | None, *, as_of: datetime | None = None,
    expected_opportunity_key: str | None = None,
) -> OpportunityDecayAssessment:
    now = _parse_time(as_of if as_of is not None else datetime.now(timezone.utc), "as_of")
    assert now is not None
    row = evidence if isinstance(evidence, Mapping) else {}
    key = row.get("opportunity_key")
    reason = None
    if not _identity(key):
        reason = "opportunity_key_missing"
    elif expected_opportunity_key is not None and key != expected_opportunity_key:
        reason = "opportunity_key_mismatch"
    try:
        if reason:
            raise ValueError(reason)
        validity = _validity(row, now)
    except (ValueError, TypeError, OverflowError) as exc:
        reason = str(exc)
        validity = dict(state="UNKNOWN", last_validated_at=None, expired_fields=(),
                        stale_by_seconds=None, blockers=(reason,))
    components = {name: _unknown(reason) if reason else _component(name, row.get(name), row, now)
                  for name in ("commercial_value", "buyer_timing", "competitive_saturation")}
    commercial = components["commercial_value"]
    return OpportunityDecayAssessment(
        opportunity_key=expected_opportunity_key or (key if _identity(key) else ""),
        as_of=now.isoformat(), evidence_refs=_refs(row), **validity, **components,
        recency_factor_candidate=commercial.get("retained_value_ratio"),
    )
