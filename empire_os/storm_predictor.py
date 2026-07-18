"""
Storm Predictor — real implementation, salvaged from Empire-USA-Strike and
predictive-cloud/api repos. Wires into the Empire OS funnel.

What it does:
1. Polls NWS (api.weather.gov) for active severe weather alerts
2. Filters for roof-damaging events: Tornado Warning, Severe Thunderstorm
   Warning, High Wind Warning
3. Stores each "strike" in the funnel as a DISCOVERED prospect, with the
   storm area description as the company/location
4. Optionally sends alerts to Discord + Telegram

Original sources (with secrets extracted):
- Empire-USA-Strike/striker_agent.py
- predictive-cloud/api/radar_nws.py
- predictive-cloud/app/api/storm/route.js
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("storm_predictor")


# Roof-damaging events we care about
ROOF_DAMAGING_EVENTS = {
    "Tornado Warning",
    "Severe Thunderstorm Warning",
    "High Wind Warning",
    "Flash Flood Warning",
}

USER_AGENT = "Empire-AI-Predictive-Revenue/1.0 (storm-predictor; contact@empire-os.local)"
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"


@dataclass
class StormEvent:
    """A severe weather event that could drive roofing demand."""
    event_id: str = ""
    event_type: str = ""          # "Tornado Warning" | "Severe Thunderstorm Warning" | ...
    severity: int = 0             # 1-5 (NWS certainty × urgency)
    area_description: str = ""
    headline: str = ""
    occurred_at: str = ""
    expires_at: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class HotZone:
    """A zip code flagged as high roofing-demand opportunity."""
    event: Optional[StormEvent] = None
    zip_codes: list = field(default_factory=list)
    demand_score: float = 0.0     # 0-100


class StormPredictor:
    """Polls NWS for severe weather, surfaces high-demand zones."""

    def __init__(
        self,
        discord_webhook_url: Optional[str] = None,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        on_strike=None,                 # callback(storm_event) -> prospect_id
        timeout: int = 15,
    ):
        self.discord_webhook_url = (
            discord_webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")
        )
        self.telegram_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = (
            telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        )
        self.on_strike = on_strike
        self.timeout = timeout
        self.last_scan_at: Optional[str] = None
        self.strikes_found: int = 0
        self.events: list = []

    # ── NWS scan ────────────────────────────────────────────────────

    def scan(self) -> list:
        """Poll NWS, return list of StormEvents for roof-damaging alerts."""
        logger.info("Initiating satellite scan for USA strike zones...")
        try:
            req = urllib.request.Request(
                NWS_ALERTS_URL,
                headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error("NWS scan failed: %s", e)
            return []

        features = data.get("features", [])
        events = []
        for f in features:
            props = f.get("properties", {})
            event_type = props.get("event", "")
            if event_type not in ROOF_DAMAGING_EVENTS:
                continue

            event = StormEvent(
                event_id=f.get("id", ""),
                event_type=event_type,
                area_description=props.get("areaDesc", "Unknown Zone"),
                headline=props.get("headline", ""),
                occurred_at=props.get("sent", ""),
                expires_at=props.get("expires", ""),
                severity=self._severity(props),
                raw=props,
            )
            events.append(event)
            self._notify(event)

        self.last_scan_at = datetime.now(timezone.utc).isoformat()
        self.strikes_found += len(events)
        self.events.extend(events)
        logger.info("Scan complete: %d strikes found", len(events))
        return events

    def _severity(self, props: dict) -> int:
        """Convert NWS certainty/urgency to 1-5 severity score."""
        certainty = props.get("certainty", "").lower()
        urgency = props.get("urgency", "").lower()
        score = 1
        if urgency == "immediate":
            score += 2
        elif urgency == "expected":
            score += 1
        if certainty == "observed":
            score += 2
        elif certainty == "likely":
            score += 1
        return min(score, 5)

    # ── Notifications ──────────────────────────────────────────────

    def _notify(self, event: StormEvent):
        """Send strike notification to Discord + Telegram + callback."""
        msg = (
            f"🚨 EMPIRE STRIKE: {event.event_type}\n"
            f"📍 Location: {event.area_description}\n"
            f"⏰ Sent: {event.occurred_at}\n"
            f"Severity: {event.severity}/5"
        )

        if self.discord_webhook_url:
            try:
                req = urllib.request.Request(
                    self.discord_webhook_url,
                    data=json.dumps({"content": msg}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                logger.debug("Discord notify failed: %s", e)

        if self.telegram_token and self.telegram_chat_id:
            try:
                import empire_os.hermes_gateway as _g
                _g._telegram_send(msg, revenue=False)
            except Exception as e:
                logger.debug("Telegram notify failed: %s", e)

        if self.on_strike:
            try:
                self.on_strike(event)
            except Exception as e:
                logger.debug("on_strike callback failed: %s", e)

    # ── AGI observe/reason/act ──────────────────────────────────────

    def observe(self) -> dict:
        return {
            "agent": "storm-predictor",
            "strikes_found_total": self.strikes_found,
            "events_tracked": len(self.events),
            "last_scan_at": self.last_scan_at,
            "last_events": [asdict(e) for e in self.events[-5:]],
        }

    def reason(self, state: dict) -> str:
        """LLM decides whether to scan now or wait."""
        return json.dumps({
            "action": "scan" if not state.get("last_scan_at") else "skip",
            "reasoning": "continuous radar monitoring",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "scan":
            events = self.scan()
            return {"action": "scan", "strikes": len(events)}
        return {"action": "skip", "summary": "maintaining radar lock"}


# ── Cinematic damage forge (the "ALI" / Runway pipeline) ───────────

def build_damage_video_prompt(zip_code: str) -> str:
    """Build the Runway prompt for cinematic damage video."""
    return (
        f"Cinematic drone shot, heavy storm damage to roof in ZIP {zip_code}, "
        "high wind, hyper-realistic, golden hour lighting."
    )


def build_satellite_url(zip_code: str, api_key: Optional[str] = None) -> str:
    """Build Google Static Maps satellite URL for a zip code."""
    key = api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return ""
    params = urllib.parse.urlencode({
        "center": zip_code,
        "zoom": "18",
        "size": "600x600",
        "maptype": "satellite",
        "key": key,
    })
    return f"https://maps.googleapis.com/maps/api/staticmap?{params}"


def build_storm_report_event(event: StormEvent) -> dict:
    """Build the ALI forged damage report payload."""
    return {
        "target_id": event.event_id,
        "business_name": event.area_description,
        "event_type": event.event_type,
        "damage_score": event.severity * 20,  # 1-5 → 20-100
        "forged_summary": (
            f"High-probability commercial roof damage detected in {event.area_description}. "
            f"Severity {event.severity}/5. Initiate outreach."
        ),
    }