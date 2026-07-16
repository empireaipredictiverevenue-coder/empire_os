"""
Homeowner Pipeline Extension (Blueprint v5 #4).

Own event table (`si_homeowner_event`) with independent state machine:

    homeowner_job → matched_to_contractor → bid_sent → bid_accepted
    → work_scheduled → work_completed → settled

Stored in its own table rather than extending the lead funnel's
`si_funnel_event`, because the ordering constraints differ and the
two pipelines should not interfere.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("homeowner_pipeline")

# ── States ──────────────────────────────────────────────────────────

HOMEOWNER_ORDER = [
    "homeowner_job",
    "matched_to_contractor",
    "bid_sent",
    "bid_accepted",
    "work_scheduled",
    "work_completed",
    "settled",
]

HOMEOWNER_STATES = frozenset(HOMEOWNER_ORDER)


# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_homeowner_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT    NOT NULL,
    from_status TEXT,
    to_status   TEXT    NOT NULL,
    actor       TEXT    NOT NULL,
    notes       TEXT    DEFAULT '',
    occurred_at TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_homeowner_job
    ON si_homeowner_event(job_id, occurred_at);
"""


# ── DTOs ────────────────────────────────────────────────────────────


@dataclass
class HomeownerEvent:
    id: int
    job_id: str
    from_status: Optional[str]
    to_status: str
    actor: str
    notes: str
    occurred_at: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "actor": self.actor,
            "notes": self.notes,
            "occurred_at": self.occurred_at,
        }


# ── Errors ──────────────────────────────────────────────────────────


class HomeownerPipelineError(Exception):
    """Base error for homeowner pipeline."""


class InvalidTransitionError(HomeownerPipelineError):
    """Raised when a transition violates ordering rules."""


class UnknownStatusError(HomeownerPipelineError):
    """Raised for unknown status strings."""


# ── Backend wrapper (reuses funnel's SQLiteBackend) ─────────────────

# Accept any object that exposes execute / commit.
# The existing funnel.SQLiteBackend qualifies.


# ── Helpers ─────────────────────────────────────────────────────────


def _validate_status(status: str) -> str:
    if status not in HOMEOWNER_STATES:
        raise UnknownStatusError(
            f"Unknown homeowner status: '{status}'. "
            f"Valid: {sorted(HOMEOWNER_STATES)}"
        )
    return status


def _status_index(status: str) -> int:
    return HOMEOWNER_ORDER.index(status)


def _make_occurred_at() -> str:
    """ISO 8601 with microsecond precision; 1 ms guard for atomicity."""
    time.sleep(0.001)
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def _current_status(backend, job_id: str) -> Optional[str]:
    cursor = backend.execute(
        "SELECT to_status FROM si_homeowner_event "
        "WHERE job_id = ? ORDER BY id DESC LIMIT 1",
        (job_id,),
    )
    row = cursor.fetchone()
    return row["to_status"] if row else None


# ── Schema management ───────────────────────────────────────────────


def ensure_schema(backend) -> None:
    """Create the si_homeowner_event table if it does not exist."""
    backend.executescript(SCHEMA_SQL)
    backend.commit()
    logger.info("si_homeowner_event schema ensured")


# ── Pipeline operations ─────────────────────────────────────────────


def transition_job(
    backend,
    job_id: str,
    from_status: str,
    to_status: str,
    actor: str = "homeowner_pipeline",
    notes: str = "",
) -> int:
    """Append an event and return the new event id.

    Validates:
    - Both statuses are known homeowner statuses.
    - No backward transitions.
    - No skip-more-than-one (except same-state, which is idempotent).
    - Current state must match ``from_status`` (caller verification).
    - Actor must be non-empty.
    """
    from_status = _validate_status(from_status)
    to_status = _validate_status(to_status)

    if not actor or not actor.strip():
        raise ValueError("Actor cannot be empty")

    current = _current_status(backend, job_id)

    # Verify caller's from_status matches reality
    if current is not None and current != from_status:
        raise ValueError(
            f"Job '{job_id}' current status is '{current}', "
            f"but caller expected '{from_status}'"
        )

    # Ordering checks
    if current is not None:
        cur_idx = _status_index(current)
        tgt_idx = _status_index(to_status)

        if tgt_idx < cur_idx:
            raise InvalidTransitionError(
                f"Backward: '{current}' → '{to_status}' for job '{job_id}'"
            )
        if tgt_idx > cur_idx + 1:
            raise InvalidTransitionError(
                f"Skip: '{current}' → '{to_status}' for job '{job_id}'. "
                f"Allowed next: '{HOMEOWNER_ORDER[cur_idx + 1]}'"
            )
        if tgt_idx == cur_idx:
            # Same-state: idempotent — return latest event id
            cursor = backend.execute(
                "SELECT id FROM si_homeowner_event "
                "WHERE job_id = ? ORDER BY id DESC LIMIT 1",
                (job_id,),
            )
            row = cursor.fetchone()
            return row["id"] if row else 0

    occurred_at = _make_occurred_at()
    cursor = backend.execute(
        """INSERT INTO si_homeowner_event
           (job_id, from_status, to_status, actor, notes, occurred_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (job_id, current, to_status, actor, notes, occurred_at),
    )
    backend.commit()
    event_id = cursor.lastrowid
    logger.info(
        "Job %s: %s → %s (event_id=%d, actor=%s)",
        job_id, from_status, to_status, event_id, actor,
    )
    return event_id


def get_job_timeline(
    backend,
    job_id: str,
) -> list[dict]:
    """Return all events for a job (oldest first)."""
    cursor = backend.execute(
        "SELECT id, job_id, from_status, to_status, actor, notes, "
        "occurred_at, created_at FROM si_homeowner_event "
        "WHERE job_id = ? ORDER BY id ASC",
        (job_id,),
    )
    return [
        {
            "id": r["id"],
            "job_id": r["job_id"],
            "from_status": r["from_status"],
            "to_status": r["to_status"],
            "actor": r["actor"],
            "notes": r["notes"],
            "occurred_at": r["occurred_at"],
        }
        for r in cursor.fetchall()
    ]


def get_pipeline_stats(
    backend,
) -> dict:
    """Return count of jobs at each homeowner pipeline status."""
    cursor = backend.execute(
        """SELECT e.to_status AS status, COUNT(*) AS cnt
           FROM si_homeowner_event e
           INNER JOIN (
               SELECT job_id, MAX(id) AS max_id
               FROM si_homeowner_event
               GROUP BY job_id
           ) l ON e.id = l.max_id
           GROUP BY e.to_status
           ORDER BY e.to_status"""
    )
    counts = {s: 0 for s in HOMEOWNER_ORDER}
    for row in cursor.fetchall():
        counts[row["status"]] = row["cnt"]
    return counts
