"""
CEO — The operator's daily decision loop.

This persona is the operator-facing surface of Empire OS. It reads the
funnel, the headline numbers, and the marketing tick, then builds the
"today" queue — a set of decisions the operator must act on.

The CEO persona is read-only with respect to outbound. It surfaces
decisions; the operator presses the buttons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from empire_os.funnel import SQLiteBackend, count_by_state

logger = logging.getLogger("ceo")


@dataclass
class Decision:
    """A decision the operator needs to make today.

    `kind` corresponds to the action type (e.g., 'ship_draft',
    'review_replied', 'review_matched').
    `priority` is lower-first: 1 = highest urgency.
    """
    kind: str
    target_id: str
    priority: int
    summary: str = ""


@dataclass
class Headline:
    """Top-line numbers for the day."""
    gross_cents: int = 0
    settled_cents: int = 0
    settlement_count: int = 0
    prospects_in_pipeline: int = 0


@dataclass
class Brief:
    """The complete daily brief for the operator."""
    date: str
    headline: dict = field(default_factory=dict)
    funnel: dict = field(default_factory=dict)
    decisions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "headline": self.headline,
            "funnel": self.funnel,
            "decisions": [d.__dict__ if hasattr(d, "__dict__") else d for d in self.decisions],
        }


def build_brief(
    backend: SQLiteBackend,
    as_of: Optional[date] = None,
    include_decisions: bool = True,
) -> Brief:
    """Build the CEO daily brief.

    This is the idempotent read-side entry point. Call it any number
    of times per day — it never writes.

    Args:
        backend: The funnel database backend.
        as_of: Override the date (defaults to today).
        include_decisions: Set False for a pure read with no decisions.

    Returns:
        A Brief object with headline, funnel, and decisions.
    """
    today = as_of or date.today()
    today_str = today.isoformat()

    # --- Funnel counts ---
    funnel_counts = count_by_state(backend)
    total_prospects = sum(funnel_counts.values())

    # --- Headline ---
    # Try to read from daily_revenue_snapshots
    gross = 0
    settled = 0
    settlement_count = 0
    try:
        cursor = backend.execute(
            "SELECT gross_cents, settled_cents, settlement_count "
            "FROM daily_revenue_snapshots WHERE snapshot_date = ?",
            (today_str,),
        )
        row = cursor.fetchone()
        if row:
            gross = row["gross_cents"]
            settled = row["settled_cents"]
            settlement_count = row["settlement_count"]
    except Exception:
        logger.debug("No daily_revenue_snapshots table yet — headline will be empty")

    headline = Headline(
        gross_cents=gross,
        settled_cents=settled,
        settlement_count=settlement_count,
        prospects_in_pipeline=total_prospects,
    )

    # --- Decisions ---
    decisions: list[Decision] = []
    if include_decisions:
        # Priority 1: prospects that have replied (awaiting CEO review/claim)
        from empire_os.funnel import list_states
        replied = list_states(backend, state="replied")
        for p in replied:
            decisions.append(Decision(
                kind="review_replied",
                target_id=p.prospect_id,
                priority=1,
                summary=f"Prospect {p.prospect_id} replied — review and claim",
            ))

        # Priority 2: newly matched prospects that need outreach drafted
        matched = list_states(backend, state="matched")
        for p in matched:
            decisions.append(Decision(
                kind="ship_draft",
                target_id=p.prospect_id,
                priority=2,
                summary=(f"Prospect {p.prospect_id} is matched "
                         f"— draft outreach"),
            ))

        # Priority 3: funnel summary
        decisions.append(Decision(
            kind="funnel_check",
            target_id="overview",
            priority=3,
            summary=f"Pipeline: {funnel_counts}",
        ))

        # Sort by priority
        decisions.sort(key=lambda d: d.priority)

    return Brief(
        date=today_str,
        headline=headline.__dict__,
        funnel=funnel_counts,
        decisions=decisions,
    )


def tick(backend: SQLiteBackend) -> None:
    """CEO tick — builds and logs the brief.

    The CEO tick writes no side effects to the funnel; it just logs
    the brief for the operator.
    """
    brief = build_brief(backend)
    logger.info(
        "CEO brief (%s): %d prospects, %d decisions, "
        "$%d gross",
        brief.date,
        brief.headline["prospects_in_pipeline"],
        len(brief.decisions),
        brief.headline["gross_cents"],
    )
