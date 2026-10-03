"""Evidence-first Digital Avatar Clone Fleet usage metering."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any, Iterable, Mapping

from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.saas_scale import UsageObservation


_METRIC = "digital_avatar_verified_meeting_session"
_PERIOD_RE = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


def _parse_time(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("usage lifecycle updated_at required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("usage lifecycle updated_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("usage lifecycle updated_at must include timezone")
    return parsed.astimezone(timezone.utc)


def _validate_runtime(runtime: AvatarFleetRuntimeBinding) -> None:
    if not runtime.tenant_id.strip() or not runtime.avatar_id.strip():
        raise ValueError("usage runtime tenant/avatar required")
    if runtime.runtime_authority != "observe":
        raise ValueError("usage runtime authority must remain observe")
    if runtime.execution_authority != "none":
        raise ValueError("usage runtime execution authority must remain none")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("usage runtime contains forbidden authority")


@dataclass(frozen=True)
class AvatarFleetVerifiedMeetingUsage:
    tenant_id: str
    avatar_id: str
    meeting_id: str
    bot_id: str
    usage_key: str
    period: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    metric: str = _METRIC
    units: int = 1
    billable_candidate: bool = True
    commercial_terms_bound: bool = False
    charge_executed: bool = False
    payment_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def validate(self) -> None:
        if not all((
            self.tenant_id.strip(),
            self.avatar_id.strip(),
            self.meeting_id.strip(),
            self.bot_id.strip(),
            self.usage_key.strip(),
        )):
            raise ValueError("verified meeting usage identity required")
        if self.metric != _METRIC or self.units != 1:
            raise ValueError("verified meeting usage metric invariant violated")
        if not _PERIOD_RE.fullmatch(self.period):
            raise ValueError("verified meeting usage period invalid")
        _parse_time(self.observed_at)
        if not self.evidence_refs:
            raise ValueError("verified meeting usage evidence required")
        if (
            self.commercial_terms_bound
            or self.charge_executed
            or self.payment_execution
            or self.revenue_recognition
            or self.execution_authority != "none"
        ):
            raise ValueError("verified meeting usage grants forbidden authority")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class AvatarFleetMonthlyUsage:
    tenant_id: str
    period: str
    observed_monthly_usage: int
    usage_keys: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    observed_at: str
    metric: str = _METRIC
    source: str = ""
    billing_execution: bool = False
    payment_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_saas_usage_observation(self) -> UsageObservation:
        observation = UsageObservation(
            tenant_id=self.tenant_id,
            metric=self.metric,
            value=self.observed_monthly_usage,
            period=self.period,
            source=self.source,
        )
        observation.validate()
        return observation


def build_verified_meeting_usage(
    *,
    runtime: AvatarFleetRuntimeBinding,
    lifecycle_state: Mapping[str, Any],
) -> AvatarFleetVerifiedMeetingUsage | None:
    _validate_runtime(runtime)

    meeting_id = str(lifecycle_state.get("meeting_id") or "").strip()
    avatar_id = str(lifecycle_state.get("avatar_id") or "").strip()
    bot_id = str(lifecycle_state.get("bot_id") or "").strip()
    if not meeting_id or not avatar_id or not bot_id:
        return None
    if avatar_id != runtime.avatar_id:
        raise PermissionError("usage lifecycle/runtime avatar mismatch")

    if str(lifecycle_state.get("execution_authority") or "").lower() != "none":
        raise ValueError("usage lifecycle grants forbidden authority")
    if lifecycle_state.get("speech_execution") is not False:
        raise ValueError("usage lifecycle speech invariant violated")
    if str(lifecycle_state.get("truth_class") or "").upper() != "VERIFIED":
        return None
    if str(lifecycle_state.get("status_code") or "").lower() != "done":
        return None
    if lifecycle_state.get("joined_meeting") is not True:
        return None
    if lifecycle_state.get("terminal") is not True:
        return None
    if lifecycle_state.get("fatal") is True:
        return None

    refs = tuple(dict.fromkeys(
        str(value or "").strip()
        for value in (lifecycle_state.get("evidence_refs") or ())
        if str(value or "").strip()
    ))
    if not refs:
        return None

    observed = _parse_time(lifecycle_state.get("updated_at"))
    period = observed.strftime("%Y-%m")
    material = "|".join((
        runtime.tenant_id,
        runtime.avatar_id,
        meeting_id,
        _METRIC,
    ))
    usage_key = "avatar-usage:" + sha256(material.encode("utf-8")).hexdigest()

    event = AvatarFleetVerifiedMeetingUsage(
        tenant_id=runtime.tenant_id,
        avatar_id=runtime.avatar_id,
        meeting_id=meeting_id,
        bot_id=bot_id,
        usage_key=usage_key,
        period=period,
        observed_at=observed.isoformat(),
        evidence_refs=refs,
    )
    event.validate()
    return event


def aggregate_verified_meeting_usage(
    *,
    tenant_id: str,
    period: str,
    events: Iterable[AvatarFleetVerifiedMeetingUsage],
) -> AvatarFleetMonthlyUsage:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("usage aggregate tenant_id required")
    if not _PERIOD_RE.fullmatch(str(period or "").strip()):
        raise ValueError("usage aggregate period invalid")

    unique: dict[str, AvatarFleetVerifiedMeetingUsage] = {}
    for event in events:
        event.validate()
        if event.tenant_id != tenant:
            raise PermissionError("usage aggregate cross-tenant event")
        if event.period != period:
            continue
        current = unique.get(event.usage_key)
        if current is not None and current != event:
            raise ValueError("usage event idempotency conflict")
        unique[event.usage_key] = event

    rows = tuple(sorted(
        unique.values(),
        key=lambda value: (value.observed_at, value.usage_key),
    ))
    if not rows:
        raise ValueError("no verified usage for period")

    latest = max(_parse_time(row.observed_at) for row in rows)
    refs = tuple(dict.fromkeys(
        ref
        for row in rows
        for ref in row.evidence_refs
    ))
    keys = tuple(row.usage_key for row in rows)
    aggregate_hash = sha256("|".join(keys).encode("utf-8")).hexdigest()

    return AvatarFleetMonthlyUsage(
        tenant_id=tenant,
        period=period,
        observed_monthly_usage=len(rows),
        usage_keys=keys,
        evidence_refs=refs,
        observed_at=latest.isoformat(),
        source=f"digital_avatar_verified_lifecycle:{aggregate_hash}",
    )
