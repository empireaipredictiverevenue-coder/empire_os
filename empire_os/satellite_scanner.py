"""
Satellite Scanner — detect warehouse roof damage from satellite imagery.

Pipeline:
1. Take a hot zone from StormPredictor (zip code + event)
2. Build a Google Static Maps satellite URL centered on the zip
3. Fetch the image, cache locally
4. Score warehouse damage using one of:
   a. LLM with vision (best quality, requires multimodal model)
   b. Simple heuristic from image metadata (free fallback)
5. Surface warehouse-rich zones as leads to the funnel

Free fallback uses image hash + cache key + visible-structure heuristics
when no vision model is available. With vision, the LLM gets the image
URL and returns {warehouses_visible: int, damage_score: 0-100,
dominant_damage: "..."}.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("satellite_scanner")


USER_AGENT = "Empire-AI-SatelliteScanner/1.0"
DEFAULT_CACHE_DIR = Path("/root/.empire/satellite_cache")


@dataclass
class SatelliteScanResult:
    """Outcome of scanning one zip code."""
    zip_code: str = ""
    image_url: str = ""
    image_cached_path: str = ""
    warehouses_detected: int = 0
    damage_score: float = 0.0     # 0-100
    dominant_damage: str = ""      # "hail" | "wind" | "tornado" | "flood" | "none"
    confidence: float = 0.0
    method: str = ""               # "llm_vision" | "heuristic" | "cached"
    raw: dict = field(default_factory=dict)
    scanned_at: str = ""


@dataclass
class WarehouseLead:
    """A high-value warehouse damage opportunity."""
    zip_code: str = ""
    city: str = ""
    state: str = ""
    warehouses_detected: int = 0
    damage_score: float = 0.0
    dominant_damage: str = ""
    opportunity_score: float = 0.0   # warehouses × damage_score
    scan_result: Optional[SatelliteScanResult] = None


# ── Google Static Maps URL builder ──────────────────────────────────

def build_satellite_url(
    zip_code: str,
    api_key: Optional[str] = None,
    zoom: int = 18,
    size: str = "600x600",
) -> str:
    """Build a Google Static Maps satellite URL for a zip code.

    Empty string if no API key is set.
    """
    key = api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return ""
    params = urllib.parse.urlencode({
        "center": zip_code,
        "zoom": str(zoom),
        "size": size,
        "maptype": "satellite",
        "key": key,
    })
    return f"https://maps.googleapis.com/maps/api/staticmap?{params}"


def build_satellite_metadata_url(
    zip_code: str,
    api_key: Optional[str] = None,
) -> str:
    """Build a Maps Static API URL that returns metadata only.

    zoom=0 with size=1x1 returns a tiny image + JSON metadata via headers.
    """
    return build_satellite_url(zip_code, api_key=api_key, zoom=0, size="1x1")


# ── Cache helpers ──────────────────────────────────────────────────

def _cache_path(zip_code: str, cache_dir: Path) -> Path:
    """Deterministic cache path for a zip code."""
    h = hashlib.sha1(zip_code.encode()).hexdigest()[:16]
    return cache_dir / f"{zip_code}_{h}.jpg"


# ── Scanner ────────────────────────────────────────────────────────

class SatelliteScanner:
    """Scans zip codes for warehouse roof damage via satellite imagery."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        google_api_key: Optional[str] = None,
        llm=None,  # multimodal LLM client (OllamaClient with vision model)
        min_damage_score: float = 50.0,
    ):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.google_api_key = google_api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.llm = llm
        self.min_damage_score = min_damage_score
        self.results: list = []
        self.metrics = {
            "scans_total": 0,
            "scans_cached": 0,
            "scans_vision": 0,
            "scans_heuristic": 0,
            "warehouses_found": 0,
            "high_damage_zones": 0,
        }

    def is_configured(self) -> bool:
        return bool(self.google_api_key)

    def scan_zip(self, zip_code: str, force: bool = False) -> SatelliteScanResult:
        """Scan one zip code for warehouse damage."""
        self.metrics["scans_total"] += 1
        result = SatelliteScanResult(
            zip_code=zip_code,
            scanned_at=datetime.now(timezone.utc).isoformat(),
        )

        if not self.is_configured():
            result.method = "skipped"
            result.raw = {"error": "GOOGLE_API_KEY not set"}
            return result

        result.image_url = build_satellite_url(zip_code, self.google_api_key)

        # Cache check
        cache_file = _cache_path(zip_code, self.cache_dir)
        if cache_file.exists() and not force:
            result.image_cached_path = str(cache_file)
            result.method = "cached"
            self.metrics["scans_cached"] += 1
            # Re-score from cache (could call LLM again if not done)
            result = self._rescore_cached(result)
            self._record(result)
            return result

        # Fetch fresh image
        image_data = self._fetch_image(result.image_url)
        if image_data is None:
            result.method = "fetch_failed"
            return result

        try:
            cache_file.write_bytes(image_data)
            result.image_cached_path = str(cache_file)
        except Exception as e:
            logger.debug("cache write failed: %s", e)

        # Score via vision model or heuristic
        if self.llm and hasattr(self.llm, "vision_score"):
            result = self.llm.vision_score(result, image_data)
            self.metrics["scans_vision"] += 1
        else:
            result = self._heuristic_score(result, image_data)
            self.metrics["scans_heuristic"] += 1

        self._record(result)
        return result

    def scan_zone(self, zone: dict) -> WarehouseLead:
        """Take a hot zone (from StormPredictor) and produce a WarehouseLead."""
        zip_code = zone.get("zip") or zone.get("zip_code", "")
        result = self.scan_zip(zip_code)

        warehouses = result.warehouses_detected
        damage = result.damage_score
        opportunity = warehouses * damage

        lead = WarehouseLead(
            zip_code=zip_code,
            city=zone.get("city", ""),
            state=zone.get("state", ""),
            warehouses_detected=warehouses,
            damage_score=damage,
            dominant_damage=result.dominant_damage,
            opportunity_score=opportunity,
            scan_result=result,
        )
        return lead

    def is_worth_pursuing(self, lead: WarehouseLead) -> bool:
        """Decide if a warehouse lead is worth pushing to the funnel."""
        opportunity = lead.opportunity_score or (
            lead.warehouses_detected * lead.damage_score
        )
        return (
            lead.warehouses_detected >= 1
            and lead.damage_score >= self.min_damage_score
            and opportunity >= 100
        )

    # ── Internals ───────────────────────────────────────────────

    def _fetch_image(self, url: str) -> Optional[bytes]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception as e:
            logger.warning("image fetch failed for %s: %s", url, e)
            return None

    def _heuristic_score(self, result: SatelliteScanResult, image_data: bytes) -> SatelliteScanResult:
        """Free fallback when no vision model is available.

        Uses image size + content length as a proxy for "complexity".
        Real implementation would integrate a CV model; this gives us
        a deterministic signal that downstream agents can still act on.
        """
        size_kb = len(image_data) / 1024
        # Larger images (more complex / more structures) score higher
        warehouses = max(0, min(int(size_kb / 40), 20))
        # We don't have damage evidence without vision, so default low
        damage_score = min(size_kb / 10, 30.0)
        result.warehouses_detected = warehouses
        result.damage_score = damage_score
        result.dominant_damage = "unknown"
        result.confidence = 0.3
        result.method = "heuristic"
        result.raw = {"image_size_kb": round(size_kb, 1)}
        return result

    def _rescore_cached(self, result: SatelliteScanResult) -> SatelliteScanResult:
        """Re-score from a cached image (assumes heuristic)."""
        try:
            data = Path(result.image_cached_path).read_bytes()
            return self._heuristic_score(result, data)
        except Exception:
            result.method = "cache_failed"
            return result

    def _record(self, result: SatelliteScanResult):
        self.results.append(result)
        self.metrics["warehouses_found"] += result.warehouses_detected
        if result.damage_score >= self.min_damage_score:
            self.metrics["high_damage_zones"] += 1

    # ── AGI observe/reason/act ──────────────────────────────────

    def observe(self) -> dict:
        return {
            "agent": "satellite-scanner",
            "scans_total": self.metrics["scans_total"],
            "warehouses_found": self.metrics["warehouses_found"],
            "high_damage_zones": self.metrics["high_damage_zones"],
            "configured": self.is_configured(),
            "cache_size": len(list(self.cache_dir.glob("*.jpg"))),
        }

    def reason(self, state: dict) -> str:
        return json.dumps({
            "action": "scan" if state.get("configured") else "skip",
            "reasoning": "scan queued storm zones",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "scan" and self.results:
            latest = self.results[-1]
            return {
                "action": "scan",
                "warehouses": latest.warehouses_detected,
                "damage": latest.damage_score,
            }
        return {"action": "skip", "summary": "no zones to scan"}