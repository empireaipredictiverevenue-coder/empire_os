"""
AGI Client — delegates agentic operations to AGI scout/marketing microservices.

Hub uses these to push LLM-powered reasoning work to dedicated containers
on empire-net while keeping orchestration local.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger("agi-client")

AGI_SCOUT_URL = "http://127.0.0.1:8000/v1/agi/scout"
AGI_MARKETING_URL = "http://127.0.0.1:8000/v1/agi/marketing"


class AgiScoutClient:
    """Client for the AGI Scout microservice (LLM-driven market intelligence)."""

    def __init__(self, base_url: str = AGI_SCOUT_URL, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._online: Optional[bool] = None

    def check_health(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def tick(self) -> dict:
        """Run one AGI Scout observe-reason-act cycle."""
        try:
            resp = requests.post(
                f"{self.base_url}/tick",
                json={},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("agi-scout tick failed: %s", e)
            return {"cycle": 0, "error": str(e)}

    def state(self) -> dict:
        """Return current AGI Scout state and cycle count."""
        try:
            resp = requests.get(f"{self.base_url}/state", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {"agent": "agi-scout", "cycle": 0, "last_result": None}


class AgiMarketingClient:
    """Client for the AGI Marketing microservice (LLM-driven content strategy)."""

    def __init__(self, base_url: str = AGI_MARKETING_URL, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._online: Optional[bool] = None

    def check_health(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def tick(self) -> dict:
        """Run one AGI Marketing observe-reason-act cycle."""
        try:
            resp = requests.post(
                f"{self.base_url}/tick",
                json={},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("agi-marketing tick failed: %s", e)
            return {"cycle": 0, "error": str(e)}

    def state(self) -> dict:
        """Return current AGI Marketing state and cycle count."""
        try:
            resp = requests.get(f"{self.base_url}/state", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {"agent": "agi-marketing", "cycle": 0, "last_result": None}

    def deploy(self, niche: str, angle_hint: str = "") -> dict:
        """Generate and deploy AEO content for a niche via the AGI agent."""
        try:
            resp = requests.post(
                f"{self.base_url}/tick",
                json={},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("agi-marketing deploy failed: %s", e)
            return {"error": str(e)}
