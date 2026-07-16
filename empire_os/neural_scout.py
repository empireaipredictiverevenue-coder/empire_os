"""
Neural Scout — Autonomous niche scanning & prospect discovery agent.

The Neural Scout is the outermost ring of the Empire OS engine. It
scouts configured niches across multiple data sources (public records,
web directories, permit portals, etc.), scores each lead for quality,
and registers discoveries in the funnel for the Traffic Specialist to
process.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from empire_os.funnel import SQLiteBackend, FunnelState, transition
from empire_os.scanner import (
    DBPRScanner,
    SunbizScanner,
    CountyAppraiserScanner,
    PermitScanner,
    BBBScanner,
    WebSearchScanner,
)

logger = logging.getLogger("neural_scout")


@dataclass
class ScoredLead:
    """A prospect that has been scored by the Neural Scout."""
    prospect_id: str
    niche: str
    source: str
    score: float
    details: str = ""
    phone: str = ""
    zip_code: str = ""
    name: str = ""
    address: str = ""
    discovered_at: str = ""


# ── Scoring ─────────────────────────────────────────────────────────

NICHE_WEIGHTS = {
    "roofing": 0.45,
    "mass_torts": 0.55,
    "hvac": 0.40,
    "electrical": 0.35,
    "plumbing": 0.38,
    "solar": 0.42,
    "pest_control": 0.30,
    "landscaping": 0.28,
}

HIGH_TICKET_KEYWORDS = [
    "warehouse", "commercial", "storm", "hail", "leak",
    "corporate", "facility", "fleet", "multi-unit",
    "condo", "apartment", "hoa", "government",
]


def calculate_synthetic_score(
    niche: str,
    details: str,
    phone: str = "",
    zip_code: str = "",
) -> float:
    """Calculate a synthetic intent score for a lead.

    Returns a float in [0.0, 1.0]. Higher = more qualified.
    """
    base_weight = NICHE_WEIGHTS.get(niche.lower(), 0.30)
    detail_len = len(details.split())
    intent_score = 0.20 if detail_len > 10 else 0.05

    keyword_matches = sum(
        1 for word in HIGH_TICKET_KEYWORDS if word in details.lower()
    )
    target_multiplier = min(keyword_matches * 0.10, 0.25)

    # Phone present bonus
    phone_bonus = 0.05 if phone and len(phone) >= 10 else 0.0

    return round(
        min(base_weight + intent_score + target_multiplier + phone_bonus, 1.0), 2
    )


# ── Scout ────────────────────────────────────────────────────────────

class NeuralScout:
    """Main Neural Scout agent.

    Usage:
        backend = SQLiteBackend("empire_os.db")
        backend.ensure_schema()
        scout = NeuralScout(backend)

        # Single lead
        lead = scout.evaluate(niche="hvac", details="...", phone="...")
        scout.register_lead(lead)

        # Tick — runs all configured scanners
        results = scout.tick()
    """

    def __init__(
        self,
        backend: SQLiteBackend,
        min_score: float = 0.30,
        actor_name: str = "neural-scout",
        auto_register: bool = True,
    ):
        self.backend = backend
        self.min_score = min_score
        self.actor_name = actor_name
        self._scanners: list = []
        if auto_register:
            self._register_default_scanners()

    def _register_default_scanners(self) -> None:
        """Register all 6 public-records scanners by default."""
        self.register_scanner(DBPRScanner())
        self.register_scanner(SunbizScanner())
        self.register_scanner(CountyAppraiserScanner())
        self.register_scanner(PermitScanner())
        self.register_scanner(BBBScanner())
        self.register_scanner(WebSearchScanner())
        logger.info(
            "NeuralScout: %d default scanners registered",
            len(self._scanners),
        )

    def register_scanner(self, scanner) -> None:
        """Register a scanner archetype."""
        self._scanners.append(scanner)

    def evaluate(
        self,
        niche: str,
        details: str,
        phone: str = "",
        zip_code: str = "",
        name: str = "",
        address: str = "",
        source: str = "web",
        prospect_id: Optional[str] = None,
    ) -> Optional[ScoredLead]:
        """Evaluate a raw lead and return a ScoredLead if it passes threshold."""
        score = calculate_synthetic_score(niche, details, phone, zip_code)
        if score < self.min_score:
            logger.info(
                "Lead below threshold: niche=%s score=%.2f min=%.2f",
                niche, score, self.min_score,
            )
            return None

        pid = prospect_id or f"lead:{niche}:{hash(details) & 0xFFFFFFFF:08x}"
        return ScoredLead(
            prospect_id=pid,
            niche=niche,
            source=source,
            score=score,
            details=details,
            phone=phone,
            zip_code=zip_code,
            name=name,
            address=address,
            discovered_at=datetime.now(timezone.utc).isoformat(),
        )

    def register_lead(self, lead: ScoredLead) -> int:
        """Register a scored lead as a discovery in the funnel.

        Also writes to si_prospect_consent with opt-in status.
        Returns the funnel event id.
        """
        # Upsert consent
        self.backend.execute(
            """INSERT OR REPLACE INTO si_prospect_consent
               (prospect_id, opted_in, opted_in_at, niche, source)
               VALUES (?, 1, ?, ?, ?)""",
            (lead.prospect_id, lead.discovered_at, lead.niche, lead.source),
        )

        # Register in funnel
        eid = transition(
            self.backend,
            prospect_id=lead.prospect_id,
            to_state=FunnelState.DISCOVERED,
            actor=self.actor_name,
            notes=(
                f"niche={lead.niche} source={lead.source} "
                f"score={lead.score} zip={lead.zip_code}"
            ),
        )
        self.backend.commit()
        logger.info(
            "Registered lead %s (niche=%s score=%.2f) as event %d",
            lead.prospect_id, lead.niche, lead.score, eid,
        )
        return eid

    def tick(self, niches: Optional[list[str]] = None) -> dict:
        """Run all registered scanners and register qualifying leads.

        Returns a summary dict with counts.
        """
        if not self._scanners:
            logger.warning("No scanners registered — Neural Scout tick is a no-op")
            return {"scanned": 0, "registered": 0, "leads": []}

        results = {"scanned": 0, "registered": 0, "leads": []}
        for scanner in self._scanners:
            leads = scanner.scan(niches=niches)
            results["scanned"] += len(leads)
            for lead in leads:
                scored = self.evaluate(
                    niche=lead.get("niche", ""),
                    details=lead.get("details", ""),
                    phone=lead.get("phone", ""),
                    zip_code=lead.get("zip_code", ""),
                    name=lead.get("name", ""),
                    address=lead.get("address", ""),
                    source=scanner.name if hasattr(scanner, "name") else "scanner",
                )
                if scored:
                    eid = self.register_lead(scored)
                    results["registered"] += 1
                    results["leads"].append({
                        "prospect_id": scored.prospect_id,
                        "niche": scored.niche,
                        "score": scored.score,
                        "event_id": eid,
                    })
        return results
