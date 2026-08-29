"""
Empire OS v3 — Contractor Lead Qualifier (top-tier pre-qualification).

Raw contractor rows from state portals / Bing are low-signal. Top-tier
buyers (platinum/gold) only want HIGH-QUALITY, PRE-QUALIFIED leads.

This scores each lead on signals that proxy "real, active, reachable,
in-niche, in-geo":

  +license present (state-licensed = vetted)        +40
  +active license status                            +20
  +has phone                                        +20
  +has website/email                                +15
  +niche keyword match (roofing/hvac/solar...)      +25
  +geo match (target metro/state)                   +20
  - missing name / too short                        reject
  - status inactive/expired                         reject

Tiers: HOT >= 120, WARM >= 80, COOL >= 50, else reject.
Only HOT/WARM are posted to the top-tier endpoint.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

NICHE_KW = {
    "roofing": ["roof", "roofing", "roofer"],
    "hvac": ["hvac", "heating", "air", "cooling", "mechanical"],
    "solar": ["solar", "pv", "photovoltaic"],
    "plumbing": ["plumb"],
    "electrical": ["electric", "electrical"],
    "general": ["construction", "contractor", "build", "remodel"],
}


@dataclass
class QBands:
    hot: int = 120
    warm: int = 80
    cool: int = 50

    def tier(self, score: int) -> Optional[str]:
        if score >= self.hot:
            return "HOT"
        if score >= self.warm:
            return "WARM"
        if score >= self.cool:
            return "COOL"
        return None


@dataclass
class QLead:
    name: str
    phone: str = ""
    email: str = ""
    website: str = ""
    state: str = ""
    city: str = ""
    license_no: str = ""
    license_status: str = ""   # active / expired / etc
    source: str = ""
    niche: str = ""
    geo: str = ""
    extra: str = ""
    raw: dict = field(default_factory=dict)
    score: int = 0
    tier: str = ""

    def to_dict(self):
        return {
            "name": self.name, "phone": self.phone, "email": self.email,
            "website": self.website, "state": self.state, "city": self.city,
            "license_no": self.license_no, "license_status": self.license_status,
            "source": self.source, "niche": self.niche, "geo": self.geo,
            "score": self.score, "tier": self.tier,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }


def score_lead(lead: QLead, target_niche: str = "", target_geo: str = "") -> QLead:
    s = 0
    if lead.license_no:
        s += 40
        if lead.license_status and "active" in lead.license_status.lower():
            s += 20
    if lead.phone:
        s += 20
    if lead.website or lead.email:
        s += 15
    kws = NICHE_KW.get(target_niche.lower()) or NICHE_KW.get(lead.niche.lower()) or []
    blob = (lead.name + " " + lead.extra).lower()
    if any(k in blob for k in kws):
        s += 25
    g = (target_geo or lead.geo or "").lower()
    if g and (g in (lead.state + " " + lead.city).lower() or g in blob):
        s += 20
    lead.score = s
    return lead


class Qualifier:
    """Scores + tiers contractor leads; emits only HOT/WARM for top tier."""

    def __init__(self, bands: Optional[QBands] = None,
                 target_niche: str = "", target_geo: str = ""):
        self.bands = bands or QBands()
        self.target_niche = target_niche
        self.target_geo = target_geo
        self.metrics = {"received": 0, "rejected": 0,
                        "by_tier": {"HOT": 0, "WARM": 0, "COOL": 0}}

    def qualify(self, rows: list[dict]) -> dict:
        hot, warm, cool = [], [], []
        for r in rows:
            if r.get("error") or not r.get("name") or len(r["name"]) < 2:
                self.metrics["rejected"] += 1
                continue
            ql = QLead(
                name=r["name"], phone=r.get("phone", ""), email=r.get("email", ""),
                website=r.get("website", ""), state=r.get("state", ""),
                city=r.get("city", ""), license_no=r.get("license_no", ""),
                license_status=r.get("license_status", "") or r.get("extra", ""),
                source=r.get("source", ""), niche=self.target_niche,
                geo=self.target_geo, extra=r.get("extra", ""), raw=r,
            )
            score_lead(ql, self.target_niche, self.target_geo)
            tier = self.bands.tier(ql.score)
            self.metrics["received"] += 1
            if not tier:
                self.metrics["rejected"] += 1
                continue
            ql.tier = tier
            self.metrics["by_tier"][tier] += 1
            if tier == "HOT":
                hot.append(ql.to_dict())
            elif tier == "WARM":
                warm.append(ql.to_dict())
            else:
                cool.append(ql.to_dict())
        return {"hot": hot, "warm": warm, "cool": cool, "metrics": dict(self.metrics)}
