"""
Empire OS v3 — Agentic Engine

Five personas operating on a shared funnel state machine:
- funnel: append-only event log (the contract between agents)
- traffic_specialist: discovery → matched
- marketing: AEO coverage gap analysis + spec drafting
- ceo: daily brief builder
- daily_revenue: settlement → snapshot pipeline

Plus:
- neural_scout: niche scanning & prospect discovery agent
- scanner: pluggable scanner archetypes for Neural Scout
- marketing_dspy: opt-in DSPy path for Marketing persona
"""

from empire_os.funnel import (
    SQLiteBackend,
    FunnelState,
    transition,
    get_state,
    events_for,
    list_states,
    count_by_state,
    FunnelEvent,
    FunnelStateRow,
    InvalidTransitionError,
    EmptyActorError,
    UnknownStateError,
)

__version__ = "0.1.0"
__all__ = [
    "SQLiteBackend",
    "FunnelState",
    "transition",
    "get_state",
    "events_for",
    "list_states",
    "count_by_state",
    "FunnelEvent",
    "FunnelStateRow",
    "InvalidTransitionError",
    "EmptyActorError",
    "UnknownStateError",
]
