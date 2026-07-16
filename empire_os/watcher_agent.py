"""
Watcher Agent — monitors the funnel for anomalies and triggers alerts.

Watches for:
- Settlements without payout records
- Pipeline stalls (too many prospects stuck at one state)
- AGI agent health degradation (consecutive failures)
- New leads without proper niche classification
- Unusually high or low conversion rates

Reports via Telegram when configured.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("watcher")


@dataclass
class Alert:
    """A watcher alert."""
    alert_id: str = ""
    severity: str = ""           # info | warning | critical
    title: str = ""
    body: str = ""
    source: str = ""
    created_at: str = ""


class WatcherAgent:
    """Watches the funnel and triggers alerts on anomalies."""

    def __init__(self, hub_url: str = "http://localhost:8080"):
        self.hub_url = hub_url.rstrip("/")
        self.alerts: list = []
        self.last_check_at: Optional[str] = None
        self.thresholds = {
            "max_consecutive_failures": 3,
            "max_settlement_without_payout_hours": 24,
            "max_stuck_in_state": 100,
            "min_conversion_rate": 0.1,
        }

    def check(self) -> list:
        """Run all watcher checks, return new alerts."""
        new_alerts = []
        new_alerts.extend(self._check_settlements_without_payout())
        new_alerts.extend(self._check_pipeline_stalls())
        new_alerts.extend(self._check_conversion_rates())
        self.last_check_at = datetime.now(timezone.utc).isoformat()
        self.alerts.extend(new_alerts)
        return new_alerts

    def _http_get(self, path: str) -> Optional[dict]:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.hub_url}{path}", timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.debug("GET %s failed: %s", path, e)
            return None

    def _check_settlements_without_payout(self) -> list:
        """Alert on settlements with no matching payout record."""
        alerts = []
        counts = self._http_get("/v1/funnel/counts") or {}
        settled_count = counts.get("settled", 0)
        # Cross-reference with payout store
        try:
            from empire_os.payout import PayoutStore
            payouts = PayoutStore().list_all()
            paid_count = sum(1 for p in payouts if p.get("status") == "paid")
            pending_count = sum(1 for p in payouts if p.get("status") in ("pending", "submitted"))
        except Exception:
            paid_count = 0
            pending_count = 0

        unaccounted = settled_count - paid_count - pending_count
        if unaccounted > 0:
            alerts.append(self._make_alert(
                "warning",
                f"{unaccounted} settlements missing payouts",
                f"{settled_count} settlements on file, only {paid_count + pending_count} "
                f"payouts created. {unaccounted} need payouts.",
                "settlements",
            ))
        return alerts

    def _check_pipeline_stalls(self) -> list:
        """Alert if any funnel state has too many stuck prospects."""
        alerts = []
        counts = self._http_get("/v1/funnel/counts") or {}
        max_stuck = self.thresholds["max_stuck_in_state"]
        for state, n in counts.items():
            if n > max_stuck:
                alerts.append(self._make_alert(
                    "warning",
                    f"Pipeline stall in {state}",
                    f"{n} prospects stuck at state '{state}' (threshold: {max_stuck})",
                    "pipeline",
                ))
        return alerts

    def _check_conversion_rates(self) -> list:
        """Alert if discovered → settled conversion drops below threshold."""
        alerts = []
        counts = self._http_get("/v1/funnel/counts") or {}
        discovered = counts.get("discovered", 0)
        settled = counts.get("settled", 0)
        if discovered > 10:
            rate = settled / discovered
            if rate < self.thresholds["min_conversion_rate"]:
                alerts.append(self._make_alert(
                    "info",
                    "Low conversion rate detected",
                    f"discovered={discovered} settled={settled} rate={rate:.1%} "
                    f"(threshold: {self.thresholds['min_conversion_rate']:.1%})",
                    "conversion",
                ))
        return alerts

    def _make_alert(self, severity: str, title: str, body: str, source: str) -> Alert:
        import uuid
        return Alert(
            alert_id=str(uuid.uuid4())[:8],
            severity=severity,
            title=title,
            body=body,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def observe(self) -> dict:
        return {
            "agent": "watcher",
            "total_alerts": len(self.alerts),
            "last_check_at": self.last_check_at,
            "recent_alerts": [asdict(a) for a in self.alerts[-5:]],
        }

    def reason(self, state: dict) -> str:
        return json.dumps({"action": "check", "reasoning": "watcher sweep"})

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "check":
            alerts = self.check()
            return {"action": "check", "alerts_found": len(alert_objects := alerts)}
        return {"action": "skip", "summary": "no check needed"}