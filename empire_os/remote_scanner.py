"""
Remote Scanner — delegates scanning operations to the scout-agent microservice.

Hub uses this to push scanner work to the dedicated scout-agent container
on empire-net while keeping the funnel + persona logic local.
"""
import logging, json
from typing import Optional
import requests

logger = logging.getLogger("remote-scanner")

SCOUT_AGENT_URL = "http://10.218.156.140:9090"  # scout-agent on empire-net

class ScoutAgentClient:
    """Client for the remote scout-agent microservice."""

    def __init__(self, base_url: str = SCOUT_AGENT_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._online: Optional[bool] = None

    def check_health(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def scan(self, niches: list[str] | None = None,
             min_score: float = 0.30) -> dict:
        """Run full scan on scout-agent, return results with scored + registered leads."""
        payload = {}
        if niches:
            payload["niches"] = niches
        payload["min_score"] = min_score
        try:
            resp = requests.post(
                f"{self.base_url}/scan",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("scout-agent scan failed: %s", e)
            return {"scanned": 0, "registered": 0, "leads": []}

    def evaluate(self, niche: str, details: str,
                 phone: str = "", zip_code: str = "",
                 name: str = "", source: str = "hub") -> dict:
        """Remote lead scoring."""
        try:
            resp = requests.post(
                f"{self.base_url}/evaluate",
                json={
                    "niche": niche,
                    "details": details,
                    "phone": phone,
                    "zip_code": zip_code,
                    "name": name,
                    "source": source,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.debug("scout-agent evaluate failed: %s", e)
            return {"qualified": False, "score": 0}

    def list_scanners(self) -> list:
        try:
            resp = requests.get(f"{self.base_url}/scanners", timeout=5)
            resp.raise_for_status()
            return resp.json().get("scanners", [])
        except requests.RequestException:
            return []

    def funnel_counts(self) -> dict:
        try:
            resp = requests.get(f"{self.base_url}/funnel/counts", timeout=5)
            resp.raise_for_status()
            return resp.json().get("counts", {})
        except requests.RequestException:
            return {}
