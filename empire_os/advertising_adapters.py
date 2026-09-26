"""Read-only provider adapter contracts for Advertising Brain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from empire_os.advertising_brain import AdPerformanceObservation


ProviderFetcher = Callable[[str, str, str], Sequence[Mapping[str, Any]]]


class AdvertisingAdapterUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AdvertisingReadStatus:
    provider: str
    enabled: bool
    configured: bool
    available: bool
    reason: str


class DisabledAdvertisingReadAdapter:
    def __init__(self, provider: str, reason: str = "disabled"):
        self.provider = provider
        self.reason = reason

    def status(self) -> AdvertisingReadStatus:
        return AdvertisingReadStatus(
            provider=self.provider,
            enabled=False,
            configured=False,
            available=False,
            reason=self.reason,
        )

    def observations(self, *, start_date: str, end_date: str):
        raise AdvertisingAdapterUnavailable(self.reason)


class InjectedAdvertisingReadAdapter:
    """Provider-neutral read adapter. Network access is injected by caller."""

    def __init__(
        self,
        provider: str,
        account_id: str,
        fetcher: ProviderFetcher,
    ):
        name = str(provider or "").strip().lower()
        if name not in {"google", "meta"}:
            raise ValueError("unsupported advertising provider")
        if not str(account_id or "").strip():
            raise ValueError("account_id required")
        self.provider = name
        self.account_id = str(account_id).strip()
        self.fetcher = fetcher

    def status(self) -> AdvertisingReadStatus:
        return AdvertisingReadStatus(
            provider=self.provider,
            enabled=True,
            configured=True,
            available=True,
            reason="injected_read_transport_ready",
        )
    def observations(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> tuple[AdPerformanceObservation, ...]:
        rows = self.fetcher(
            self.account_id,
            str(start_date),
            str(end_date),
        )
        if not isinstance(rows, Sequence):
            raise AdvertisingAdapterUnavailable(
                "advertising read transport returned invalid payload"
            )

        observations: list[AdPerformanceObservation] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise AdvertisingAdapterUnavailable(
                    "advertising read row must be a mapping"
                )
            campaign_id = str(row.get("campaign_id") or "").strip()
            observed_at = str(row.get("observed_at") or "").strip()
            if not campaign_id or not observed_at:
                raise AdvertisingAdapterUnavailable(
                    "campaign_id and observed_at are required"
                )
            observations.append(AdPerformanceObservation(
                platform=self.provider,
                campaign_id=campaign_id,
                creative_id=(
                    str(row["creative_id"]).strip()
                    if row.get("creative_id") is not None
                    else None
                ),
                spend_cents=int(row.get("spend_cents") or 0),
                attributed_revenue_cents=(
                    int(row["attributed_revenue_cents"])
                    if row.get("attributed_revenue_cents") is not None
                    else None
                ),
                attributed_gross_profit_cents=(
                    int(row["attributed_gross_profit_cents"])
                    if row.get("attributed_gross_profit_cents") is not None
                    else None
                ),
                impressions=(
                    int(row["impressions"])
                    if row.get("impressions") is not None
                    else None
                ),
                clicks=(
                    int(row["clicks"])
                    if row.get("clicks") is not None
                    else None
                ),
                conversions=(
                    int(row["conversions"])
                    if row.get("conversions") is not None
                    else None
                ),
                observed_at=observed_at,
                source=f"{self.provider}_ads_injected_read_transport",
            ))
        return tuple(observations)
