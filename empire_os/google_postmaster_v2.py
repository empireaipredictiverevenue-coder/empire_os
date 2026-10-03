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



def default_metric_definitions() -> list[dict[str, object]]:
    """Current Gmail Postmaster v2 metrics relevant to Ringleader."""
    return [
        {
            "name": "spam_rate",
            "baseMetric": {"standardMetric": "SPAM_RATE"},
        },
        {
            "name": "spf_success_rate",
            "baseMetric": {"standardMetric": "AUTH_SUCCESS_RATE"},
            "filter": 'auth_type = "spf"',
        },
        {
            "name": "dkim_success_rate",
            "baseMetric": {"standardMetric": "AUTH_SUCCESS_RATE"},
            "filter": 'auth_type = "dkim"',
        },
        {
            "name": "dmarc_success_rate",
            "baseMetric": {"standardMetric": "AUTH_SUCCESS_RATE"},
            "filter": 'auth_type = "dmarc"',
        },
        {
            "name": "tls_outbound_rate",
            "baseMetric": {"standardMetric": "TLS_ENCRYPTION_RATE"},
            "filter": 'traffic_direction = "outbound"',
        },
        {
            "name": "reject_error_rate",
            "baseMetric": {"standardMetric": "DELIVERY_ERROR_RATE"},
            "filter": 'error_type = "reject"',
        },
        {
            "name": "temp_fail_error_rate",
            "baseMetric": {"standardMetric": "DELIVERY_ERROR_RATE"},
            "filter": 'error_type = "temp_fail"',
        },
    ]


def normalize_compliance_status(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert Google compliance evidence to a bounded Ringleader signal."""

    spf = dict(payload.get("spfStatus") or payload.get("spf_status") or {})
    dkim = dict(payload.get("dkimStatus") or payload.get("dkim_status") or {})
    dmarc = dict(payload.get("dmarcStatus") or payload.get("dmarc_status") or {})
    verdict = dict(
        payload.get("deliverabilityStatusVerdict")
        or payload.get("deliverability_status_verdict")
        or {}
    )

    def _state(value: Mapping[str, Any]) -> str:
        nested = value.get("state")
        if isinstance(nested, Mapping):
            return str(nested.get("state") or nested.get("status") or "").upper()
        return str(nested or value.get("status") or "").upper()

    reason = str(verdict.get("reason") or "").upper()
    verdict_state = _state(verdict)

    hard_reasons = {
        "SPAM_RATE_HIGH",
        "SENDER_NOT_COMPLIANT",
        "SMTP_ERRORS_HIGH",
    }
    evidence_holds = []
    if not spf:
        evidence_holds.append("gmail_spf_compliance_unknown")
    if not dkim:
        evidence_holds.append("gmail_dkim_compliance_unknown")
    if not dmarc:
        evidence_holds.append("gmail_dmarc_compliance_unknown")

    if reason in hard_reasons:
        posture = "HOLD_GMAIL"
    elif reason == "MESSAGE_VOLUME_LOW":
        posture = "OBSERVE"
    elif verdict_state and "COMPLIANT" not in verdict_state:
        posture = "LIMIT_GMAIL"
    else:
        posture = "GREEN"

    return {
        "posture": posture,
        "reason": reason or None,
        "spf_state": _state(spf) or None,
        "dkim_state": _state(dkim) or None,
        "dmarc_state": _state(dmarc) or None,
        "deliverability_state": verdict_state or None,
        "evidence_holds": evidence_holds,
        "scope": "gmail_destination_only",
    }
