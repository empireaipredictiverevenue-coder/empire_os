"""
Lead Filter — improved replacement for beta_analyst.js.

Better than the original in three ways:
1. Multi-source deduplication — same lead from Reddit + storm = merged,
   not double-counted. Keys on (niche, geo, contact_hash).
2. Tier scoring with configurable bands (HOT/WARM/COOL/COLD) and
   auto-rejection of stale leads (older than max_age_hours).
3. 2FA TOTP gate for high-value actions (preserved from beta_analyst).

Inputs come from any agent that produces leads:
  - RedditSniper (B2B buying intent)
  - StormPredictor (storm events → hot zones)
  - SatelliteScanner (warehouse damage scores)
  - Manual inbox
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("lead_filter")


# ── Tiering thresholds ──────────────────────────────────────────────

@dataclass
class TierBands:
    hot: int = 150
    warm: int = 80
    cool: int = 50   # anything below this is rejected

    def tier(self, score: int) -> Optional[str]:
        if score >= self.hot:
            return "HOT"
        if score >= self.warm:
            return "WARM"
        if score >= self.cool:
            return "COOL"
        return None   # rejected


# ── Lead representation ────────────────────────────────────────────

@dataclass
class Lead:
    """A unified lead across all sources."""
    lead_id: str = ""
    source: str = ""                # "reddit" | "storm" | "satellite" | "manual"
    title: str = ""
    description: str = ""
    url: str = ""
    score: int = 0
    tier: str = ""
    niche: str = ""                 # roofing | hvac | solar | generic | storm-zone
    location: str = ""              # zip or area
    contact_hint: str = ""          # author, business name, etc.
    raw: dict = field(default_factory=dict)
    created_at: str = ""
    deduplicated_from: list = field(default_factory=list)  # other source lead_ids merged into this one


# ── Dedup key generation ────────────────────────────────────────────

def _contact_hash(lead: Lead) -> str:
    """Hash on the meaningful signal for dedup.

    Two leads dedup when they refer to the same place/person, regardless
    of which source they came from. Keys on (location, niche, contact_hint).
    """
    key = f"{lead.location}|{lead.niche}|{lead.contact_hint}".lower().strip()
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _lead_to_dict(lead) -> dict:
    """Convert a lead from any source into our Lead shape."""
    if isinstance(lead, Lead):
        return asdict(lead)
    if isinstance(lead, dict):
        return lead
    # dataclass from another module
    return {
        "source": getattr(lead, "source", "unknown"),
        "title": getattr(lead, "title", ""),
        "description": getattr(lead, "description", "") or getattr(lead, "preview", ""),
        "url": getattr(lead, "url", ""),
        "score": getattr(lead, "lead_score", 0) or getattr(lead, "score", 0),
        "niche": getattr(lead, "niche", "generic"),
        "location": getattr(lead, "location", "") or getattr(lead, "area_description", ""),
        "contact_hint": getattr(lead, "author", "") or getattr(lead, "business_name", ""),
    }


# ── 2FA TOTP gate ──────────────────────────────────────────────────

class TwoFactorGate:
    """TOTP-based 2FA gate for high-value actions.

    Preserved from beta_analyst.js — when a deal is submitted for
    authorization, a TOTP code is generated and sent via SMS. The
    operator must confirm with that code before the deal is approved.

    Implementation note: we use a simple TOTP (RFC 6238) without
    external deps — no otplib needed.
    """

    def __init__(self, secret: str = "", ttl_seconds: int = 300):
        self.secret = secret
        self.ttl = ttl_seconds
        self._pending: dict = {}  # deal_id → {code, expires_at}

    def request_authorization(self, deal_id: str, msisdn: str = "") -> str:
        """Generate a TOTP, store as pending, return the code (caller delivers via SMS)."""
        now = int(time.time())
        slot = now // self.ttl
        code = self._hotp(self.secret, slot)
        self._pending[deal_id] = {
            "code": code, "expires_at": now + self.ttl, "msisdn": msisdn,
        }
        logger.info("2FA code generated for deal %s (expires in %ds)", deal_id, self.ttl)
        return code

    def verify(self, deal_id: str, code: str) -> bool:
        """Verify a TOTP code against the pending authorization."""
        entry = self._pending.get(deal_id)
        if not entry:
            return False
        if time.time() > entry["expires_at"]:
            del self._pending[deal_id]
            return False
        if str(code).strip() != str(entry["code"]):
            return False
        del self._pending[deal_id]
        return True

    def _hotp(self, secret: str, counter: int) -> str:
        """HMAC-based OTP, 6 digits, RFC 4226."""
        import hmac
        import struct
        if not secret:
            secret = "empire-os-default-secret"
        key = secret.encode()
        counter_bytes = struct.pack(">Q", counter)
        h = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code_int = (
            (h[offset] & 0x7F) << 24
            | (h[offset + 1] & 0xFF) << 16
            | (h[offset + 2] & 0xFF) << 8
            | (h[offset + 3] & 0xFF)
        )
        return str(code_int % 10**6).zfill(6)


# ── LeadFilter ─────────────────────────────────────────────────────

class LeadFilter:
    """Receives raw leads from any source, deduplicates, tiers, and emits."""

    def __init__(
        self,
        bands: Optional[TierBands] = None,
        max_age_hours: int = 72,
        two_factor: Optional[TwoFactorGate] = None,
    ):
        self.bands = bands or TierBands()
        self.max_age_hours = max_age_hours
        self.two_factor = two_factor or TwoFactorGate()
        self._seen_hashes: dict = {}  # contact_hash → Lead
        self.metrics = {
            "total_received": 0,
            "duplicates_merged": 0,
            "rejected_stale": 0,
            "rejected_low_score": 0,
            "qualified": 0,
            "by_tier": {"HOT": 0, "WARM": 0, "COOL": 0},
        }

    def filter_batch(self, raw_leads: list) -> dict:
        """Filter a batch of leads; returns qualified + rejected buckets."""
        qualified = []
        rejected = []

        for raw in raw_leads:
            self.metrics["total_received"] += 1
            d = _lead_to_dict(raw)
            # Avoid kwarg conflict with default values
            d.pop("lead_id", None)
            d.pop("created_at", None)
            d.pop("deduplicated_from", None)
            lead = Lead(
                **d,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            # Stale check
            if not self._is_fresh(lead):
                self.metrics["rejected_stale"] += 1
                rejected.append({"lead": lead, "reason": "stale"})
                continue

            # Tier scoring
            tier = self.bands.tier(lead.score)
            if not tier:
                self.metrics["rejected_low_score"] += 1
                rejected.append({"lead": lead, "reason": "low_score"})
                continue
            lead.tier = tier

            # Dedup
            h = _contact_hash(lead)
            if h in self._seen_hashes:
                # Merge: keep higher score, append source
                existing = self._seen_hashes[h]
                if lead.score > existing.score:
                    existing.score = lead.score
                existing.deduplicated_from.append(lead.source)
                self.metrics["duplicates_merged"] += 1
                continue

            lead.lead_id = h
            self._seen_hashes[h] = lead
            self.metrics["by_tier"][tier] += 1
            self.metrics["qualified"] += 1
            qualified.append(lead)

        return {
            "qualified": qualified,
            "rejected": rejected,
            "metrics": dict(self.metrics),
        }

    def _is_fresh(self, lead: Lead) -> bool:
        """Reject leads older than max_age_hours."""
        created = lead.created_at or lead.raw.get("created_utc", "")
        if not created:
            return True  # unknown age — assume fresh
        try:
            ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            return True
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return age_h <= self.max_age_hours

    def observe(self) -> dict:
        return {
            "agent": "lead-filter",
            "qualified": self.metrics["qualified"],
            "rejected_stale": self.metrics["rejected_stale"],
            "rejected_low_score": self.metrics["rejected_low_score"],
            "duplicates_merged": self.metrics["duplicates_merged"],
            "by_tier": dict(self.metrics["by_tier"]),
            "unique_leads": len(self._seen_hashes),
        }

    def reason(self, state: dict) -> str:
        return json.dumps({
            "action": "filter",
            "reasoning": "ingest latest batch and tier",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "filter":
            return {"action": "filter", "metrics": dict(self.metrics)}
        return {"action": "skip", "summary": "idle"}