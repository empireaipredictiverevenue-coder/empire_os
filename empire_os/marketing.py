"""
Marketing — AEO coverage gap analysis & spec drafting.

This persona is the operator of the AEO content loop. It:
1. Scans the coverage matrix to find zero/under-pages niches
2. Picks the highest-leverage gap
3. Drafts an AEO spec for that niche
4. Registers the niche as 'discovered' in the funnel

The actual LLM is the typist, not the author — the marketing persona
orchestrates the draft and the operator reviews before anything lands
on the AEO surface.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from empire_os.funnel import (
    SQLiteBackend,
    FunnelState,
    transition,
)

logger = logging.getLogger("marketing")

# Default pages-per-niche when no surface_root is provided
NICHES = [
    "roofing", "hvac", "electrical", "plumbing",
    "mass_torts", "solar", "pest_control", "landscaping",
]

DEFAULT_PAGES_PER_NICHE: dict[str, int] = {n: 0 for n in NICHES}


# ── Spec Draft ─────────────────────────────────────────────────────────


@dataclass
class AeoSpecDraft:
    """A draft AEO spec for a niche.

    The operator must review and replace DRAFT placeholders
    before the renderer ships the page.
    """
    niche: str
    target_audience: str = "DRAFT — replace with audience description"
    pain_points: str = "DRAFT — list top 3-5 pain points"
    key_questions: str = "DRAFT — what users search for"
    content_angle: str = "DRAFT — unique angle"
    tone: str = "DRAFT — professional / authoritative / local-friendly"
    word_count_target: int = 1500
    competitors: str = "DRAFT — list competing pages targeting this niche"
    internal_links: str = "DRAFT — related pages on site"
    body_html: str = ""
    meta_description: str = ""
    call_to_action: str = ""

    def to_dict(self) -> dict:
        return {
            "niche": self.niche,
            "target_audience": self.target_audience,
            "pain_points": self.pain_points,
            "key_questions": self.key_questions,
            "content_angle": self.content_angle,
            "tone": self.tone,
            "word_count_target": self.word_count_target,
            "competitors": self.competitors,
            "internal_links": self.internal_links,
            "body_html": self.body_html,
            "meta_description": self.meta_description,
            "call_to_action": self.call_to_action,
        }


@dataclass
class CoverageGap:
    """A gap in AEO coverage for a niche with discovery metrics."""
    niche: str
    page_count: int
    discovered_count: int = 0
    leverage_score: float = 0.0


@dataclass
class GapAnalysis:
    """Result of comparing existing AEO pages to the niche coverage target."""
    niche: str
    has_page: bool
    page_count: int = 0


# ── Coverage logic ────────────────────────────────────────────────────


def coverage_matrix(backend: Optional[SQLiteBackend] = None) -> list[CoverageGap]:
    """Build coverage matrix with page counts and funnel discovery data."""
    import json
    pages = set()
    try:
        from empire_os.aeo_surface import list_pages
        pages = {p["niche"] for p in list_pages()}
    except Exception:
        pass

    gaps: list[CoverageGap] = []
    for niche in NICHES:
        discovered = 0
        if backend:
            try:
                from empire_os.funnel import events_for
                for ev in events_for(backend, f"niche:{niche}") or []:
                    if "aeo_discovery" in (ev.notes or ""):
                        discovered += 1
            except Exception:
                pass
        page_count = 1 if niche in pages else 0
        leverage = (discovered / max(len(NICHES), 1)) * (1 - page_count)
        gaps.append(CoverageGap(
            niche=niche,
            page_count=page_count,
            discovered_count=discovered,
            leverage_score=round(leverage, 2),
        ))
    return gaps


def build_coverage_matrix() -> dict[str, int]:
    """Return the default pages-per-niche dict (backward compat)."""
    return dict(DEFAULT_PAGES_PER_NICHE)


def pick_highest_gap(gaps: list[CoverageGap]) -> CoverageGap | None:
    """Return the uncovered niche with the most discoveries (or first)."""
    uncovered = [g for g in gaps if g.page_count == 0]
    if not uncovered:
        return None
    return max(uncovered, key=lambda g: g.discovered_count)


def coverage_gap(surface_root: Optional[str] = None,
                 backend: Optional[SQLiteBackend] = None) -> list[GapAnalysis]:
    """Return a list of GapAnalysis for each configured niche."""
    from empire_os.aeo_surface import list_pages
    existing = {p["niche"] for p in list_pages(surface_root)}
    return [
        GapAnalysis(niche=n, has_page=(n in existing),
                     page_count=1 if n in existing else 0)
        for n in NICHES
    ]


def draft_spec_for_niche(
    backend: Optional[SQLiteBackend],
    niche: str,
) -> AeoSpecDraft:
    """Create a skeleton spec for a given niche (operator fills DRAFT fields)."""
    return AeoSpecDraft(niche=niche)


def register_discovery(backend: SQLiteBackend, niche: str) -> Optional[int]:
    """Register niche as 'discovered' in the funnel. Returns event id."""
    eid = transition(backend, f"niche:{niche}",
                     FunnelState.DISCOVERED,
                     "marketing",
                     notes="aeo_discovery")
    return eid


def tick(backend: SQLiteBackend,
         surface_root: Optional[str] = None) -> dict:
    """Run one marketing tick: gap analysis → pick niche → draft spec."""
    gaps = coverage_gap(surface_root)
    uncovered = [g for g in gaps if not g.has_page]

    if not uncovered:
        return {
            "ticked": True,
            "scanned": len(NICHES),
            "action": "no_gaps",
            "niche": None,
            "target_niche": None,
            "drafts": 0,
            "registered": [],
        }

    niche = uncovered[0].niche
    spec = draft_spec_for_niche(backend, niche)
    eid = register_discovery(backend, niche)

    return {
        "ticked": True,
        "scanned": len(NICHES),
        "action": "drafted",
        "niche": niche,
        "target_niche": niche,
        "drafts": 1,
        "registered": [niche] if eid else [],
        "spec": spec.to_dict(),
    }
