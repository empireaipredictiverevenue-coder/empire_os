"""Phase 16 SaaS evidence freshness and quota readiness review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SaasEvidenceFreshness:
    usage_age_seconds: float
    subscription_age_seconds: float
    isolation_age_seconds: float
    usage_freshness: str
    subscription_freshness: str
    isolation_freshness: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SaasQuotaReadiness:
    tenant_id: str
    observed_monthly_usage: int
    observed_usage_limit: int | None
    utilization_ratio: float | None
    remaining_units: int | None
    quota_state: str
    quota_review_ready: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    provisioning_execution: bool = False
    billing_execution: bool = False
    subscription_mutation: bool = False
    api_key_issuance: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SaasFreshnessQuotaReview:
    freshness: SaasEvidenceFreshness
    quota: SaasQuotaReadiness
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    provisioning_execution: bool = False
    billing_execution: bool = False
    subscription_mutation: bool = False
    api_key_issuance: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "freshness": self.freshness.as_dict(),
            "quota": self.quota.as_dict(),
            "mode": self.mode,
            "execution_authority": self.execution_authority,
            "provisioning_execution": self.provisioning_execution,
            "billing_execution": self.billing_execution,
            "subscription_mutation": self.subscription_mutation,
            "api_key_issuance": self.api_key_issuance,
        }


def _parse_timestamp(value: str, *, name: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{name} timestamp required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{name} timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _state(age: float, max_age_seconds: int) -> str:
    if age < -60:
        return "future"
    if age > max_age_seconds:
        return "stale"
    return "fresh"


def review_saas_quota_readiness(
    *,
    tenant_id: str,
    observed_monthly_usage: int,
    observed_usage_limit: int | None,
    active_subscription: bool,
    tenant_isolation_verified: bool,
    usage_observed_at: str,
    subscription_observed_at: str,
    isolation_observed_at: str,
    now: datetime,
    max_age_seconds: int = 21600,
) -> SaasFreshnessQuotaReview:
    tid = str(tenant_id or "").strip()
    if not tid:
        raise ValueError("tenant_id required")
    if observed_monthly_usage < 0:
        raise ValueError("observed_monthly_usage must be nonnegative")
    if observed_usage_limit is not None and observed_usage_limit < 0:
        raise ValueError("observed_usage_limit must be nonnegative")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    clock = now.astimezone(timezone.utc)
    usage_time = _parse_timestamp(
        usage_observed_at, name="usage_observed_at"
    )
    subscription_time = _parse_timestamp(
        subscription_observed_at, name="subscription_observed_at"
    )
    isolation_time = _parse_timestamp(
        isolation_observed_at, name="isolation_observed_at"
    )

    usage_age = (clock - usage_time).total_seconds()
    subscription_age = (clock - subscription_time).total_seconds()
    isolation_age = (clock - isolation_time).total_seconds()

    usage_state = _state(usage_age, max_age_seconds)
    subscription_state = _state(subscription_age, max_age_seconds)
    isolation_state = _state(isolation_age, max_age_seconds)
    freshness = SaasEvidenceFreshness(
        usage_age_seconds=round(usage_age, 3),
        subscription_age_seconds=round(subscription_age, 3),
        isolation_age_seconds=round(isolation_age, 3),
        usage_freshness=usage_state,
        subscription_freshness=subscription_state,
        isolation_freshness=isolation_state,
    )

    blockers: list[str] = []
    for name, status in (
        ("usage", usage_state),
        ("subscription", subscription_state),
        ("isolation", isolation_state),
    ):
        if status != "fresh":
            blockers.append(f"{name}_evidence_{status}")

    if not active_subscription:
        blockers.append("active_subscription_required")
    if not tenant_isolation_verified:
        blockers.append("tenant_isolation_not_verified")
    if observed_usage_limit is None:
        blockers.append("observed_usage_limit_missing")

    utilization = None
    remaining = None
    quota_state = "unknown"
    if observed_usage_limit is not None:
        remaining = max(observed_usage_limit - observed_monthly_usage, 0)
        if observed_usage_limit == 0:
            blockers.append("observed_usage_limit_zero")
            quota_state = "exhausted"
        else:
            utilization = round(
                observed_monthly_usage / observed_usage_limit,
                4,
            )
            if observed_monthly_usage > observed_usage_limit:
                blockers.append("observed_usage_over_limit")
                quota_state = "over_limit"
            elif observed_monthly_usage == observed_usage_limit:
                quota_state = "exhausted"
            else:
                quota_state = "available"

    ordered = tuple(sorted(set(blockers)))
    quota = SaasQuotaReadiness(
        tenant_id=tid,
        observed_monthly_usage=observed_monthly_usage,
        observed_usage_limit=observed_usage_limit,
        utilization_ratio=utilization,
        remaining_units=remaining,
        quota_state=quota_state,
        quota_review_ready=not ordered,
        blockers=ordered,
    )
    return SaasFreshnessQuotaReview(
        freshness=freshness,
        quota=quota,
    )
