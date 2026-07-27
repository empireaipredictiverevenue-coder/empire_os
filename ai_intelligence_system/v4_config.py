#!/usr/bin/env python3
"""
v4_config.py — single source of truth for V4 paths and thresholds.

All v4 modules read from here. No hardcoded paths scattered across files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


EMPIRE_ROOT = Path("/root/empire_os")
DB_PATH = EMPIRE_ROOT / "empire_os.db"
AGENT_REGISTRY = EMPIRE_ROOT / "config" / "agent_registry.json"
FEEDBACK_DIR = Path("/root/feedback")
LANE_LEADS_LIMIT = int(os.environ.get("V4_LANE_LEADS_LIMIT", "50"))


@dataclass(frozen=True)
class OmegaTier:
    """Tier thresholds for the omega score (REAL 0.0-1.0 fraction)."""

    threshold: float
    label: str


OMEGA_TIERS: tuple[OmegaTier, ...] = (
    # Thresholds match the REAL omega_score scale: 0.0 - 1.0 (fraction),
    # NOT 0 - 100. lane_leads.omega_score is a SQLite REAL with min 0.08,
    # max 1.0, avg 0.66. Anything in 0-1 against a 0-100 tier grid is all
    # T4_COLD — which is what we saw in the first V4 status pull.
    OmegaTier(0.8, "T1_HOT"),
    OmegaTier(0.6, "T2_WARM"),
    OmegaTier(0.4, "T3_COOL"),
    OmegaTier(0.0, "T4_COLD"),
)


def tier_for_score(score: float) -> str:
    """Map a 0.0-1.0 omega score to its tier label."""
    for t in OMEGA_TIERS:
        if score >= t.threshold:
            return t.label
    return "T4_COLD"
