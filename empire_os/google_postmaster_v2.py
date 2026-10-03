"""Low-level read-only Gmail Postmaster Tools API v2 adapter."""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

import requests


class GooglePostmasterV2Provider:
    BASE_URL = "https://gmailpostmastertools.googleapis.com/v2"

    def __init__(self, access_token: str, *, timeout_s: float = 10.0) -> None:
        if not access_token.strip():
            raise ValueError("postmaster_access_token_required")
        self.access_token = access_token.strip()
        self.timeout_s = timeout_s

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def compliance_status(self, domain: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.BASE_URL}/domains/{domain}/complianceStatus",
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("postmaster_invalid_compliance_payload")
        return payload

    def query_domain_stats(
        self,
        domain: str,
        *,
        start_date: date,
        end_date: date,
        metric_definitions: Iterable[Mapping[str, Any]],
        aggregation_granularity: str = "DAILY",
        page_size: int = 200,
    ) -> dict[str, Any]:
        body = {
            "metricDefinitions": [dict(item) for item in metric_definitions],
            "timeQuery": {
                "startDate": {
                    "year": start_date.year,
                    "month": start_date.month,
                    "day": start_date.day,
                },
                "endDate": {
                    "year": end_date.year,
                    "month": end_date.month,
                    "day": end_date.day,
                },
            },
            "pageSize": min(200, max(1, int(page_size))),
            "aggregationGranularity": aggregation_granularity,
        }
        response = requests.post(
            f"{self.BASE_URL}/domains/{domain}/domainStats:query",
            json=body,
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("postmaster_invalid_stats_payload")
        return payload
