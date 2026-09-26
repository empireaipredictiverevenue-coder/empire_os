"""Core contracts for Empire's evidence-first data plane.

These are pure validation/preview primitives. They persist nothing and grant no
production authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


PRIVACY_CLASSES = {
    "PUBLIC",
    "INTERNAL",
    "COMMERCIAL",
    "PII",
    "PAYMENT_EVIDENCE",
    "SECRET",
}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
VERSION_RE = re.compile(r"^v[0-9]+(?:\.[0-9]+){0,2}$")
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{2,159}$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_time(value: Any, field: str) -> datetime:
    text = _text(value)
    if not text:
        raise ValueError(f"{field} required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def canonical_payload_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RawEvidenceRef:
    evidence_ref: str
    source_key: str
    content_sha256: str
    media_type: str
    byte_size: int
    collected_at: str
    privacy_class: str
    immutable: bool = True

    def validate(self) -> None:
        if not KEY_RE.fullmatch(self.evidence_ref):
            raise ValueError("invalid evidence_ref")
        if not KEY_RE.fullmatch(self.source_key):
            raise ValueError("invalid source_key")
        if not SHA256_RE.fullmatch(self.content_sha256):
            raise ValueError("content_sha256 must be lowercase sha256")
        if not self.media_type.strip():
            raise ValueError("media_type required")
        if self.byte_size < 0:
            raise ValueError("byte_size must be non-negative")
        _parse_time(self.collected_at, "collected_at")
        if self.privacy_class not in PRIVACY_CLASSES:
            raise ValueError("unsupported privacy_class")
        if self.immutable is not True:
            raise ValueError("raw evidence must be immutable")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "execution_authority": "none",
            "storage_mutation": False,
        }


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    schema_version: str
    source_key: str
    observed_at: str
    emitted_at: str
    correlation_id: str
    idempotency_key: str
    evidence_refs: tuple[str, ...]
    payload: Mapping[str, Any]
    causation_id: str | None = None
    tenant_id: str | None = None

    def validate(self) -> None:
        for name, value in (
            ("event_id", self.event_id),
            ("event_type", self.event_type),
            ("aggregate_type", self.aggregate_type),
            ("aggregate_id", self.aggregate_id),
            ("source_key", self.source_key),
            ("correlation_id", self.correlation_id),
            ("idempotency_key", self.idempotency_key),
        ):
            if not _text(value):
                raise ValueError(f"{name} required")
        if not VERSION_RE.fullmatch(self.schema_version):
            raise ValueError("schema_version must look like v1 or v1.2")
        observed = _parse_time(self.observed_at, "observed_at")
        emitted = _parse_time(self.emitted_at, "emitted_at")
        if emitted < observed:
            raise ValueError("emitted_at cannot precede observed_at")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        if not self.evidence_refs:
            raise ValueError("event requires evidence_refs")
        if any(not _text(ref) for ref in self.evidence_refs):
            raise ValueError("evidence_refs cannot contain empty values")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "tenant_id": self.tenant_id,
            "schema_version": self.schema_version,
            "source_key": self.source_key,
            "observed_at": _parse_time(self.observed_at, "observed_at").isoformat(),
            "emitted_at": _parse_time(self.emitted_at, "emitted_at").isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "idempotency_key": self.idempotency_key,
            "evidence_refs": list(self.evidence_refs),
            "payload_hash": canonical_payload_hash(self.payload),
            "payload": dict(self.payload),
            "execution_authority": "none",
            "persisted": False,
        }


@dataclass(frozen=True)
class LineageRun:
    run_id: str
    transformation_key: str
    transformation_version: str
    code_commit: str
    started_at: str
    completed_at: str
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    input_count: int
    output_count: int
    rejected_count: int
    quarantined_count: int
    cost_cents: int | None = None

    def validate(self) -> None:
        if not _text(self.run_id):
            raise ValueError("run_id required")
        if not KEY_RE.fullmatch(self.transformation_key):
            raise ValueError("invalid transformation_key")
        if not VERSION_RE.fullmatch(self.transformation_version):
            raise ValueError("invalid transformation_version")
        if not _text(self.code_commit):
            raise ValueError("code_commit required")
        started = _parse_time(self.started_at, "started_at")
        completed = _parse_time(self.completed_at, "completed_at")
        if completed < started:
            raise ValueError("completed_at cannot precede started_at")
        if not self.input_refs:
            raise ValueError("input_refs required")
        if not self.output_refs and self.output_count:
            raise ValueError("output_refs required when output_count > 0")
        for value in (
            self.input_count,
            self.output_count,
            self.rejected_count,
            self.quarantined_count,
        ):
            if value < 0:
                raise ValueError("lineage counts must be non-negative")
        if self.rejected_count + self.quarantined_count > self.input_count:
            raise ValueError("rejected + quarantined cannot exceed input_count")
        if self.cost_cents is not None and self.cost_cents < 0:
            raise ValueError("cost_cents must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        accepted = self.input_count - self.rejected_count - self.quarantined_count
        return {
            **asdict(self),
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "accepted_input_count": accepted,
            "execution_authority": "none",
            "persisted": False,
        }


@dataclass(frozen=True)
class PointInTimeFeature:
    feature_key: str
    entity_type: str
    entity_id: str
    feature_version: str
    transformation_version: str
    feature_time: str
    materialized_at: str
    value: Any
    source_refs: tuple[str, ...]
    outcome_time: str | None = None
    privacy_class: str = "INTERNAL"

    def validate(self) -> None:
        if not KEY_RE.fullmatch(self.feature_key):
            raise ValueError("invalid feature_key")
        if not _text(self.entity_type) or not _text(self.entity_id):
            raise ValueError("entity_type and entity_id required")
        if not VERSION_RE.fullmatch(self.feature_version):
            raise ValueError("invalid feature_version")
        if not VERSION_RE.fullmatch(self.transformation_version):
            raise ValueError("invalid transformation_version")
        feature_time = _parse_time(self.feature_time, "feature_time")
        materialized = _parse_time(self.materialized_at, "materialized_at")
        if materialized < feature_time:
            raise ValueError("materialized_at cannot precede feature_time")
        if not self.source_refs:
            raise ValueError("source_refs required")
        if self.privacy_class not in PRIVACY_CLASSES:
            raise ValueError("unsupported privacy_class")
        if self.outcome_time:
            outcome = _parse_time(self.outcome_time, "outcome_time")
            if outcome <= feature_time:
                raise ValueError("outcome_time must occur after feature_time")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "source_refs": list(self.source_refs),
            "point_in_time_correct": True,
            "future_outcome_leakage": False,
            "execution_authority": "none",
            "persisted": False,
        }


def build_raw_evidence_ref(data: Mapping[str, Any]) -> dict[str, Any]:
    ref = RawEvidenceRef(
        evidence_ref=_text(data.get("evidence_ref")),
        source_key=_text(data.get("source_key")),
        content_sha256=_text(data.get("content_sha256")).lower(),
        media_type=_text(data.get("media_type")),
        byte_size=int(data.get("byte_size", -1)),
        collected_at=_text(data.get("collected_at")),
        privacy_class=_text(data.get("privacy_class")).upper(),
        immutable=data.get("immutable") is True,
    )
    return ref.as_dict()


def build_event_envelope(data: Mapping[str, Any]) -> dict[str, Any]:
    envelope = EventEnvelope(
        event_id=_text(data.get("event_id")),
        event_type=_text(data.get("event_type")),
        aggregate_type=_text(data.get("aggregate_type")),
        aggregate_id=_text(data.get("aggregate_id")),
        tenant_id=_text(data.get("tenant_id")) or None,
        schema_version=_text(data.get("schema_version")),
        source_key=_text(data.get("source_key")),
        observed_at=_text(data.get("observed_at")),
        emitted_at=_text(data.get("emitted_at")),
        correlation_id=_text(data.get("correlation_id")),
        causation_id=_text(data.get("causation_id")) or None,
        idempotency_key=_text(data.get("idempotency_key")),
        evidence_refs=tuple(
            _text(ref) for ref in data.get("evidence_refs", ()) if _text(ref)
        ),
        payload=dict(data.get("payload") or {}),
    )
    return envelope.as_dict()


def build_lineage_run(data: Mapping[str, Any]) -> dict[str, Any]:
    run = LineageRun(
        run_id=_text(data.get("run_id")),
        transformation_key=_text(data.get("transformation_key")),
        transformation_version=_text(data.get("transformation_version")),
        code_commit=_text(data.get("code_commit")),
        started_at=_text(data.get("started_at")),
        completed_at=_text(data.get("completed_at")),
        input_refs=tuple(_text(v) for v in data.get("input_refs", ()) if _text(v)),
        output_refs=tuple(_text(v) for v in data.get("output_refs", ()) if _text(v)),
        input_count=int(data.get("input_count", 0)),
        output_count=int(data.get("output_count", 0)),
        rejected_count=int(data.get("rejected_count", 0)),
        quarantined_count=int(data.get("quarantined_count", 0)),
        cost_cents=(
            int(data["cost_cents"])
            if data.get("cost_cents") is not None
            else None
        ),
    )
    return run.as_dict()


def build_point_in_time_feature(data: Mapping[str, Any]) -> dict[str, Any]:
    feature = PointInTimeFeature(
        feature_key=_text(data.get("feature_key")),
        entity_type=_text(data.get("entity_type")),
        entity_id=_text(data.get("entity_id")),
        feature_version=_text(data.get("feature_version")),
        transformation_version=_text(data.get("transformation_version")),
        feature_time=_text(data.get("feature_time")),
        materialized_at=_text(data.get("materialized_at")),
        value=data.get("value"),
        source_refs=tuple(
            _text(ref) for ref in data.get("source_refs", ()) if _text(ref)
        ),
        outcome_time=_text(data.get("outcome_time")) or None,
        privacy_class=_text(data.get("privacy_class") or "INTERNAL").upper(),
    )
    return feature.as_dict()
