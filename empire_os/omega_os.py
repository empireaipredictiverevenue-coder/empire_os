"""Omega OS — 8-area lead qualification engine.

Scores every lead across 8 dimensions:

  1.  LEAD QUALITY       — fit signals, intent level, completeness
  2.  SPEED & SCALE      — response time, batchability, volume potential
  3.  AI INTELLIGENCE    — qualification accuracy, data richness
  4.  REVENUE OPTIMIZATION — estimated value, close probability, LTV
  5.  AUTOMATION         — autonomous handoff potential, workflow fit
  6.  ANALYTICS & INSIGHT — trackability, actionability
  7.  INTEGRATION        — CRM syncability, channel readiness
  8.  SELF-LEARNING      — feedback loop potential

Final score 0-100 determines lead tier:
  PLATINUM (90+):  Immediate warm transfer to firm
  GOLD (70-89):    Qualified — deliver with intent score
  SILVER (40-69):  Raw lead — store for batch delivery
  BRONZE (<40):    Needs more data — hold for enrichment
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("omega_os")

# ── Scoring weights ──────────────────────────────────────────────────

WEIGHTS = {
    "lead_quality": 0.20,
    "speed_scale": 0.10,
    "ai_intelligence": 0.15,
    "revenue_optimization": 0.20,
    "automation": 0.10,
    "analytics_insight": 0.10,
    "integration": 0.05,
    "self_learning": 0.10,
}

# ── Score tiers ──────────────────────────────────────────────────────

TIERS = [
    ("platinum", 90, "Immediate warm transfer to subscribing firm"),
    ("gold", 70, "Qualified lead delivered with intent score"),
    ("silver", 40, "Raw lead stored for batch delivery"),
    ("bronze", 0, "Needs enrichment — hold for more data"),
]


def tier_for(score: float) -> tuple[str, str]:
    for name, threshold, desc in TIERS:
        if score >= threshold:
            return name, desc
    return "bronze", "Needs enrichment"


# ── Omega Score — full 8-dimension evaluation ────────────────────────

class OmegaScore:
    """Evaluates a lead across all 8 Omega OS dimensions."""

    def __init__(self, tort_key: str, details: str = "",
                 screening_answers: dict = None,
                 source: str = "web",
                 has_phone: bool = False,
                 has_zip: bool = False,
                 has_name: bool = False):
        self.tort = tort_key
        self.details = details
        self.screening = screening_answers or {}
        self.source = source
        self.has_phone = has_phone
        self.has_zip = has_zip
        self.has_name = has_name
        self.detail_len = len(details or "")

    def _text_len_score(self) -> float:
        """How much detail was provided about the case."""
        if self.detail_len > 200:
            return 1.0
        if self.detail_len > 100:
            return 0.7
        if self.detail_len > 50:
            return 0.4
        return 0.2

    def _contact_completeness(self) -> float:
        """How complete is the contact information."""
        score = 0.0
        if self.has_name: score += 0.35
        if self.has_phone: score += 0.40
        if self.has_zip: score += 0.25
        return score

    def _intent_signals(self) -> float:
        """Positive intent signals in the lead text."""
        signals = [
            "lawsuit", "sue", "attorney", "lawyer", "case",
            "compensation", "settlement", "claim", "legal help",
            "diagnosed", "cancer", "injury",
        ]
        text_lower = self.details.lower()
        hits = sum(1 for s in signals if s in text_lower)
        return min(hits / 5.0, 1.0)

    # ── Dimension scoring ────────────────────────────────────────

    def lead_quality_score(self) -> float:
        """1. Lead Quality Engine — fit, intent, completeness."""
        s = 0.0
        s += self._contact_completeness() * 0.4
        s += self._intent_signals() * 0.35
        s += self._text_len_score() * 0.25
        return min(s, 1.0)

    def speed_scale_score(self) -> float:
        """2. Speed & Scale — can this be batched/automated."""
        # Web and referral sources are fast; direct calls are fastest
        source_speed = {
            "web": 0.7,
            "reddit": 0.6,
            "storm": 0.8,
            "referral": 0.9,
            "direct": 1.0,
            "batch": 0.5,
        }
        return source_speed.get(self.source, 0.5)

    def ai_intelligence_score(self) -> float:
        """3. AI Intelligence — data richness for AI processing."""
        s = 0.0
        # Screening answers = structured data (highest value)
        if self.screening:
            answered = sum(1 for v in self.screening.values() if v and str(v).strip())
            s += min(answered / 3.0, 1.0) * 0.5
        # Detail text = NLP enrichment potential
        s += self._text_len_score() * 0.3
        # Source-based intelligence
        if self.source in ("web", "direct"):
            s += 0.2
        return min(s, 1.0)

    def revenue_optimization_score(self) -> float:
        """4. Revenue Optimization — estimated value × close probability.

        Different tort types have different average settlements.
        """
        # Base value from niche type
        # Mass torts have known settlement values; other niches use contract estimates
        LIKELY_VALUE = {
            "camp_lejeune": 350000, "roundup": 250000, "paraquat": 300000,
            "afff": 400000, "zantac": 150000, "ozempic": 100000,
            "nec_formula": 3000000, "3m_earplugs": 35000, "hair_relaxers": 200000,
            "talcum_powder": 150000, "hernia_mesh": 100000, "philips_cpap": 200000,
            # Non-tort services (average contract value)
            "electrical": 5000, "hvac": 8000, "plumbing": 4000, "roofing": 12000,
            "pest_control": 3000, "landscaping": 5000,
            "weight_loss": 2000, "hormone_therapy": 3000, "dental": 3000,
            "vision": 1000, "pt_rehab": 2000, "addiction": 15000,
            "marketing": 3000, "web_dev": 8000, "accounting": 2000, "consulting": 5000,
            "staffing": 500, "legal_services": 3000,
            "real_estate": 10000, "mortgage": 3000, "insurance": 1000,
            "investing": 5000, "debt_relief": 2000, "tax_prep": 500,
            "managed_it": 5000, "cybersecurity": 10000, "software_dev": 20000,
            "cloud": 15000, "ai_automation": 25000, "data_analytics": 15000,
        }
        base_value = LIKELY_VALUE.get(self.tort, 5000)
        # Normalize: $500K+ → 1.0, $5K → 0.2
        value_score = min(base_value / 250000, 1.0) * 0.8 + 0.2

        # Close probability based on contact completeness
        close_prob = self._contact_completeness() * 0.6 + self._intent_signals() * 0.4

        return value_score * 0.5 + close_prob * 0.5

    def automation_score(self) -> float:
        """5. Automation — how autonomously this can be processed."""
        s = 0.0
        # Web leads with screening = fully automated
        if self.source == "web" and self.screening:
            s += 0.5
        elif self.source in ("reddit", "storm"):
            s += 0.3
        # Complete contact info = automated routing
        s += self._contact_completeness() * 0.3
        # Structured details = automated qualification
        s += self._text_len_score() * 0.2
        return min(s, 1.0)

    def analytics_insight_score(self) -> float:
        """6. Analytics & Insight — trackability."""
        s = 0.0
        s += (0.4 if self.source != "unknown" else 0.1)
        s += (0.3 if self.has_name else 0.1)
        s += self._text_len_score() * 0.3
        return min(s, 1.0)

    def integration_score(self) -> float:
        """7. Integration — CRM/channel readiness."""
        s = 0.0
        # Name + phone + ZIP = CRM ready
        if self.has_name and self.has_phone:
            s += 0.5
        elif self.has_name:
            s += 0.3
        if self.has_zip:
            s += 0.2
        # Screening answers = CRM enrichment ready
        if self.screening:
            s += 0.3
        return min(s, 1.0)

    def self_learning_score(self) -> float:
        """8. Self-Learning — feedback loop potential.

        Leads with rich data can train the model.
        """
        s = 0.0
        s += self._text_len_score() * 0.4
        if self.screening:
            s += 0.3
        s += (0.3 if self.source in ("web", "direct") else 0.1)
        return min(s, 1.0)

    # ── Composite ────────────────────────────────────────────────

    def compute(self) -> dict:
        """Compute the full Omega score across all 8 dimensions."""
        dimensions = {
            "lead_quality": self.lead_quality_score(),
            "speed_scale": self.speed_scale_score(),
            "ai_intelligence": self.ai_intelligence_score(),
            "revenue_optimization": self.revenue_optimization_score(),
            "automation": self.automation_score(),
            "analytics_insight": self.analytics_insight_score(),
            "integration": self.integration_score(),
            "self_learning": self.self_learning_score(),
        }

        total = sum(
            dimensions[k] * WEIGHTS[k] for k in WEIGHTS
        ) * 100.0

        tier, description = tier_for(total)

        return {
            "total": round(total, 1),
            "tier": tier,
            "tier_description": description,
            "dimensions": {k: round(v * 100, 1) for k, v in dimensions.items()},
        }


# ── Batch qualification ─────────────────────────────────────────────

def qualify_prospect(backend, prospect_id: str, tort_key: str = None,
                     details: str = "", source: str = "web",
                     name: str = "", phone: str = "", zip_code: str = "",
                     screening: dict = None) -> dict:
    """Run a prospect through the full Omega qualification pipeline.

    Returns the Omega score, updates the prospect's funnel state.
    """
    # Auto-detect niche if not provided
    if not tort_key:
        from empire_os.lane_router import match_niche
        matches = match_niche(details or "")
        if matches:
            tort_key = matches[0][0]
        else:
            tort_key = "unknown"

    # Build score
    omega = OmegaScore(
        tort_key=tort_key,
        details=details,
        screening_answers=screening,
        source=source,
        has_phone=bool(phone),
        has_zip=bool(zip_code),
        has_name=bool(name),
    )
    result = omega.compute()

    # Store score in funnel
    from empire_os.funnel import transition as funnel_transition
    if backend:
        note = f"omega_score={result['total']} tier={result['tier']} tort={tort_key} src={source}"
        try:
            backend.execute(
                "INSERT INTO si_funnel_events (prospect_id, actor, state, notes) "
                "VALUES (?, 'omega_os', 'qualified', ?)",
                (prospect_id, note),
            )
            backend.commit()
        except Exception:
            pass  # non-fatal if table not available

    result["tort_key"] = tort_key
    return result


def qualify_batch(backend, lead_list: list[dict]) -> list[dict]:
    """Score multiple leads at once."""
    results = []
    for lead in lead_list:
        r = qualify_prospect(
            backend,
            prospect_id=lead.get("prospect_id", "unknown"),
            tort_key=lead.get("tort_key"),
            details=lead.get("details", ""),
            source=lead.get("source", "web"),
            name=lead.get("name", ""),
            phone=lead.get("phone", ""),
            zip_code=lead.get("zip", ""),
            screening=lead.get("screening"),
        )
        results.append(r)
    return results
