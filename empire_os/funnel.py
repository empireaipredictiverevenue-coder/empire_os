"""
Funnel — append-only event log; the contract between all Empire OS personas.

Every persona that advances a prospect writes to `si_funnel_event` via
`transition()`. The funnel is the shared state machine that serialises
all agent activity.

States (in order):
  DISCOVERED → MATCHED → OUTREACH_DRAFTED → OUTREACH_SENT → REPLIED → CLAIMED → SETTLED
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Load /root/empire_os/.env into os.environ if not already set, so
# per-process toggles like EXCLUDE_TEST_FROM_FUNNEL_COUNTS work even
# when the parent shell didn't source .env. Idempotent: existing
# os.environ keys are not overwritten.
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for _ln in _ENV_PATH.read_text().splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass


class FunnelState(str, Enum):
    DISCOVERED = "discovered"
    MATCHED = "matched"
    OUTREACH_DRAFTED = "outreach_drafted"
    OUTREACH_SENT = "outreach_sent"
    REPLIED = "replied"
    CLAIMED = "claimed"
    SETTLED = "settled"
    BILLED = "billed"        # invoice generated post-settlement
    COLLECTED = "collected"  # payment received
    DONE = "done"            # fully closed


FUNNEL_ORDER = [s.value for s in FunnelState]

# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_funnel_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id TEXT    NOT NULL,
    from_state  TEXT,
    to_state    TEXT    NOT NULL,
    actor       TEXT    NOT NULL,
    notes       TEXT    DEFAULT '',
    occurred_at TEXT    NOT NULL,   -- ISO 8601 with microseconds
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_funnel_prospect
    ON si_funnel_event(prospect_id, occurred_at);

CREATE TABLE IF NOT EXISTS si_prospect_consent (
    prospect_id TEXT PRIMARY KEY,
    opted_in    INTEGER NOT NULL DEFAULT 1,
    opted_in_at TEXT,
    niche       TEXT,
    source      TEXT
);
"""


# ── Data transfer objects ───────────────────────────────────────────

@dataclass
class FunnelEvent:
    id: int
    prospect_id: str
    from_state: Optional[str]
    to_state: str
    actor: str
    notes: str
    occurred_at: str
    created_at: str


@dataclass
class FunnelStateRow:
    prospect_id: str
    current_state: str
    actor: str
    occurred_at: str


# ── Error types ─────────────────────────────────────────────────────

class FunnelError(Exception):
    """Base funnel error."""


class InvalidTransitionError(FunnelError):
    """Raised when a transition violates funnel invariants."""


class EmptyActorError(FunnelError):
    """Raised when transition is attempted with empty actor."""


class UnknownStateError(FunnelError):
    """Raised when an unknown state is referenced."""


# ── Backend ──────────────────────────────────────────────────────────

class SQLiteBackend:
    """Thin wrapper around a SQLite connection for the funnel.

    Usage:
        backend = SQLiteBackend("empire_os.db")
        backend.ensure_schema()
    """

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")

    def ensure_schema(self) -> None:
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    @property
    def conn(self):
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params: list) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params)

    def executescript(self, sql: str) -> None:
        self._conn.executescript(sql)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ── Funnel operations ───────────────────────────────────────────────

def _validate_state(state: str) -> str:
    """Validate that a state string is a known funnel state."""
    if state not in FUNNEL_ORDER:
        raise UnknownStateError(f"Unknown funnel state: '{state}'. "
                                f"Valid: {', '.join(FunnelState.__members__)}")
    return state


def _state_index(state: str) -> int:
    return FUNNEL_ORDER.index(state)


def _make_occurred_at() -> str:
    """Return ISO 8601 timestamp with microsecond precision.

    Uses a 1ms sleep guard to ensure atomicity between the read of the
    current state and the new insert in transition(). Two transitions in
    the same microsecond would produce identical timestamps.
    """
    _sleep_until_after(0.001)  # 1 ms guard
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def _sleep_until_after(seconds: float) -> None:
    """Busy-sleep guard. Only called in transition()."""
    time.sleep(seconds)


def transition(
    backend: SQLiteBackend,
    prospect_id: str,
    to_state: str,
    actor: str,
    notes: str = "",
) -> int:
    """Append a funnel event and return the new event id.

    Invariants enforced:
    - Backward transitions: rejected.
    - Skip-more-than-one: rejected.
    - Same-state: idempotent (returns latest event id, no new row).
    - Empty actor: rejected.
    - Unknown state: rejected.
    """
    to_state = _validate_state(to_state)

    if not actor or not actor.strip():
        raise EmptyActorError("Actor cannot be empty")

    # Read current state
    current = _current_state(backend, prospect_id)

    if current is not None:
        cur_idx = _state_index(current)
        tgt_idx = _state_index(to_state)

        if tgt_idx < cur_idx:
            raise InvalidTransitionError(
                f"Backward transition: '{current}' → '{to_state}' "
                f"for prospect '{prospect_id}'"
            )
        if tgt_idx > cur_idx + 1:
            raise InvalidTransitionError(
                f"Skip-more-than-one: '{current}' → '{to_state}' "
                f"for prospect '{prospect_id}'. Allowed next: "
                f"'{FUNNEL_ORDER[cur_idx + 1]}'"
            )
        if tgt_idx == cur_idx:
            # Same-state: idempotent — return latest event id
            cursor = backend.execute(
                "SELECT id FROM si_funnel_event "
                "WHERE prospect_id = ? ORDER BY id DESC LIMIT 1",
                (prospect_id,),
            )
            row = cursor.fetchone()
            return row["id"] if row else 0

    occurred_at = _make_occurred_at()
    cursor = backend.execute(
        """INSERT INTO si_funnel_event
           (prospect_id, from_state, to_state, actor, notes, occurred_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (prospect_id, current, to_state, actor, notes, occurred_at),
    )
    backend.commit()
    return cursor.lastrowid


def get_state(backend: SQLiteBackend, prospect_id: str) -> Optional[FunnelStateRow]:
    """Return the current funnel state for a prospect, or None."""
    row = _current_state(backend, prospect_id)
    if row is None:
        return None

    # Fetch the latest event for details
    cursor = backend.execute(
        "SELECT actor, occurred_at FROM si_funnel_event "
        "WHERE prospect_id = ? ORDER BY id DESC LIMIT 1",
        (prospect_id,),
    )
    event = cursor.fetchone()
    return FunnelStateRow(
        prospect_id=prospect_id,
        current_state=row,
        actor=event["actor"] if event else "unknown",
        occurred_at=event["occurred_at"] if event else "",
    )


def _current_state(backend: SQLiteBackend, prospect_id: str) -> Optional[str]:
    """Read the current funnel state for a prospect from the event log."""
    cursor = backend.execute(
        "SELECT to_state FROM si_funnel_event "
        "WHERE prospect_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (prospect_id,),
    )
    row = cursor.fetchone()
    return row["to_state"] if row else None


def events_for(backend: SQLiteBackend, prospect_id: str) -> list[FunnelEvent]:
    """Return the full audit trail (oldest first) for a prospect."""
    cursor = backend.execute(
        "SELECT id, prospect_id, from_state, to_state, actor, notes, "
        "occurred_at, created_at FROM si_funnel_event "
        "WHERE prospect_id = ? ORDER BY id ASC",
        (prospect_id,),
    )
    return [FunnelEvent(**dict(r)) for r in cursor.fetchall()]


def list_states(
    backend: SQLiteBackend,
    state: Optional[str] = None,
    limit: int = 10_000,
) -> list[FunnelStateRow]:
    """List all prospects and their current funnel state.

    If `state` is provided, filter to prospects at that state.
    """
    if state is not None:
        _validate_state(state)

    # Get latest event per prospect via subquery
    cursor = backend.execute(
        """SELECT e.prospect_id, e.to_state AS current_state,
                  e.actor, e.occurred_at
           FROM si_funnel_event e
           INNER JOIN (
               SELECT prospect_id, MAX(id) AS max_id
               FROM si_funnel_event
               GROUP BY prospect_id
           ) l ON e.id = l.max_id
           WHERE (? IS NULL OR e.to_state = ?)
           ORDER BY e.occurred_at DESC
           LIMIT ?""",
        (state, state, limit),
    )
    return [FunnelStateRow(**dict(r)) for r in cursor.fetchall()]


def count_by_state(backend: SQLiteBackend) -> dict[str, int]:
    """Return a map of state → count for all prospects.

    Operational truth filter:
      When env EXCLUDE_TEST_FROM_FUNNEL_COUNTS=on (the operator default
      for mainnet), we drop any prospect whose si_prospect_consent.source
      is 'test' (the canonical synthetic-data marker). Prospects with NO
      consent row are kept — they're either real discoveries that
      haven't opted into consent yet, OR unobserved rows; either way
      they aren't flagged as test data, so they count.

      When the env var is unset / off, this is unchanged: it counts
      everything (used during testing phases).
    """
    exclude_test = os.environ.get(
        "EXCLUDE_TEST_FROM_FUNNEL_COUNTS", "").lower().strip() in (
        "1", "true", "yes", "on")
    if exclude_test:
        sql = """SELECT e.to_state AS state, COUNT(*) AS cnt
                 FROM si_funnel_event e
                 INNER JOIN (
                     SELECT prospect_id, MAX(id) AS max_id
                     FROM si_funnel_event
                     GROUP BY prospect_id
                 ) l ON e.id = l.max_id
                 LEFT JOIN si_prospect_consent p
                     ON p.prospect_id = e.prospect_id
                 WHERE (p.source IS NULL OR p.source != 'test')
                 GROUP BY e.to_state
                 ORDER BY e.to_state"""
    else:
        sql = """SELECT e.to_state AS state, COUNT(*) AS cnt
                 FROM si_funnel_event e
                 INNER JOIN (
                     SELECT prospect_id, MAX(id) AS max_id
                     FROM si_funnel_event
                     GROUP BY prospect_id
                 ) l ON e.id = l.max_id
                 GROUP BY e.to_state
                 ORDER BY e.to_state"""
    cursor = backend.execute(sql)
    counts = {s.value: 0 for s in FunnelState}
    for row in cursor.fetchall():
        counts[row["state"]] = row["cnt"]
    return counts
