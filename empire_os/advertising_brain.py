"""Phase 9 Advertising Brain observation and profit-math foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class AdPerformanceObservation:
    platform: str
    campaign_id: str
    creative_id: str | None
    spend_cents: int
    attributed_revenue_cents: int | None
    attributed_gross_profit_cents: int | None
    impressions: int | None
    clicks: int | None
    conversions: int | None
    observed_at: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def roas(self) -> float | None:
        if self.spend_cents <= 0 or self.attributed_revenue_cents is None:
            return None
        return self.attributed_revenue_cents / self.spend_cents

    @property
    def profit_roas(self) -> float | None:
        if self.spend_cents <= 0 or self.attributed_gross_profit_cents is None:
            return None
        return self.attributed_gross_profit_cents / self.spend_cents
def _validate_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("observed_at is required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include timezone")
    return raw


def _nonnegative_int(name: str, value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be nonnegative")
    return parsed


def normalise_ad_observation(
    row: Mapping[str, Any],
) -> AdPerformanceObservation:
    platform = str(row.get("platform") or "").strip().lower()
    campaign_id = str(row.get("campaign_id") or "").strip()
    observed_at = _validate_timestamp(row.get("observed_at"))
    source = str(row.get("source") or "").strip()
    if platform not in {"google", "meta", "tiktok", "linkedin", "other"}:
        raise ValueError("unsupported ad platform")
    if not campaign_id or not source:
        raise ValueError("campaign_id and source are required")

    spend = _nonnegative_int("spend_cents", row.get("spend_cents"))
    if spend is None:
        raise ValueError("spend_cents is required")

    return AdPerformanceObservation(
        platform=platform,
        campaign_id=campaign_id,
        creative_id=(
            str(row["creative_id"]).strip()
            if row.get("creative_id") is not None
            else None
        ),
        spend_cents=spend,
        attributed_revenue_cents=_nonnegative_int(
            "attributed_revenue_cents",
            row.get("attributed_revenue_cents"),
        ),
        attributed_gross_profit_cents=_nonnegative_int(
            "attributed_gross_profit_cents",
            row.get("attributed_gross_profit_cents"),
        ),
        impressions=_nonnegative_int("impressions", row.get("impressions")),
        clicks=_nonnegative_int("clicks", row.get("clicks")),
        conversions=_nonnegative_int("conversions", row.get("conversions")),
        observed_at=observed_at,
        source=source,
    )
