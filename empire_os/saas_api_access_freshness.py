"""Phase 16 freshness gate for API access readiness evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.saas_api_access import ApiAccessReadiness


@dataclass(frozen=True)
class ApiAccessFreshnessReview:
    tenant_id: str
    user_id: str
    fresh_for_issuance_review: bool
    ages_seconds: dict[str, float]
    blockers: tuple[str, ...]
    readiness: ApiAccessReadiness
    approval_required: bool = True
    execution_authority: str = "none"
    api_key_issuance: bool = False
    api_key_revocation: bool = False
    secret_material_generated: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["readiness"] = self.readiness.as_dict()
        return data


def _parse(value: str, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)



def assess_api_access_freshness(
    *,
    readiness: ApiAccessReadiness,
    membership_observed_at: str,
    subscription_observed_at: str,
    isolation_observed_at: str,
    now: datetime,
    max_age_seconds: int = 21600,
) -> ApiAccessFreshnessReview:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    current = now.astimezone(timezone.utc)
    blockers = list(readiness.blockers)
    ages: dict[str, float] = {}

    for label, raw in (
        ("membership", membership_observed_at),
        ("subscription", subscription_observed_at),
        ("isolation", isolation_observed_at),
    ):
        observed = _parse(raw, label=f"{label}_observed_at")
        age = (current - observed).total_seconds()
        ages[label] = round(age, 3)
        if age < -60:
            blockers.append(f"{label}_evidence_from_future")
        elif age > max_age_seconds:
            blockers.append(f"{label}_evidence_stale")

    ordered = tuple(sorted(set(blockers)))
    return ApiAccessFreshnessReview(
        tenant_id=readiness.tenant_id,
        user_id=readiness.user_id,
        fresh_for_issuance_review=readiness.issuance_ready and not ordered,
        ages_seconds=ages,
        blockers=ordered,
        readiness=readiness,
    )
