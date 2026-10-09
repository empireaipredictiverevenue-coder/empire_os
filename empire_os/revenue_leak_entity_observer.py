"""Entity-level Revenue Leak observer.

Canonical lineage:

    outbound_events / outbound_replies
        -> outbound_intents
        -> entity_id
        -> observed revenue_leak candidate

This module is deliberately OBSERVE-only.

It does not:
- infer tenant ownership,
- recognize revenue,
- estimate lost revenue,
- authorize outreach,
- create commercial terms,
- execute payments,
- persist intelligence signals.

Tenant/entity authority must be attached later by the trusted
Economic Signal reader/materializer boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from uuid import UUID


COMMERCIAL_REPLY_CLASSES = frozenset(
    {"positive", "question", "objection"}
)

SCHEMA_VERSION = "empire.revenue-leak-observation.v1"
TRUTH_CLASS = "OBSERVED"


def _uuid(value: Any, field: str) -> str:
    text = str(value or "").strip()
    try:
        return str(UUID(text))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{field} must be UUID") from exc


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return value.astimezone(timezone.utc)


def _classification(value: Any) -> str:
    return str(value or "").strip().lower()


@dataclass(frozen=True)
class RevenueLeakObservation:
    entity_id: str
    window_start: datetime
    window_end: datetime
    delivered_count: int
    commercial_reply_count: int
    evidence_refs: tuple[str, ...]

    @property
    def signal_type(self) -> str:
        return "revenue_leak"

    @property
    def truth_class(self) -> str:
        return TRUTH_CLASS

    @property
    def schema_version(self) -> str:
        return SCHEMA_VERSION

    @property
    def execution_authority(self) -> str:
        return "none"

    @property
    def commercial_authority(self) -> str:
        return "none"

    @property
    def payment_authority(self) -> str:
        return "none"

    @property
    def traffic_authority(self) -> str:
        return "none"

    @property
    def review_required(self) -> bool:
        return True

    @property
    def observed_zero_conversion(self) -> bool:
        return (
            self.delivered_count > 0
            and self.commercial_reply_count == 0
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "truth_class": self.truth_class,
            "signal_type": self.signal_type,
            "entity_id": self.entity_id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "delivered_count": self.delivered_count,
            "commercial_reply_count": self.commercial_reply_count,
            "observed_zero_conversion": self.observed_zero_conversion,
            "evidence_refs": list(self.evidence_refs),
            "execution_authority": self.execution_authority,
            "commercial_authority": self.commercial_authority,
            "payment_authority": self.payment_authority,
            "traffic_authority": self.traffic_authority,
            "review_required": self.review_required,
            # Deliberately unknown until independently evidenced.
            "lost_revenue_cents": None,
            "expected_revenue_cents": None,
            "conversion_value_cents": None,
        }


def observe_entity_revenue_leaks(
    *,
    intents: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    replies: Iterable[Mapping[str, Any]],
    start: datetime,
    end: datetime,
) -> list[RevenueLeakObservation]:
    """Produce deterministic entity-level observed funnel leakage.

    A candidate requires:
      * a canonical outbound intent with entity_id,
      * >=1 delivered event in the bounded window,
      * zero commercial replies in that same bounded window.

    Unsubscribes, bounces and suppressions are not commercial replies and
    do not create fabricated conversion evidence.

    No tenant identity is accepted here. Tenant authority is intentionally
    outside this observer.
    """

    start = _utc(start, "start")
    end = _utc(end, "end")

    if end <= start:
        raise ValueError("end must be after start")

    if end - start > timedelta(days=31):
        raise ValueError("observation window exceeds 31 days")

    intent_entity: dict[str, str] = {}

    for raw in intents:
        intent_id = _uuid(raw.get("id"), "intent.id")

        entity_raw = raw.get("entity_id")
        if entity_raw in (None, ""):
            continue

        entity_id = _uuid(entity_raw, "intent.entity_id")

        existing = intent_entity.get(intent_id)
        if existing is not None and existing != entity_id:
            raise ValueError(
                f"conflicting entity lineage for intent {intent_id}"
            )

        intent_entity[intent_id] = entity_id

    delivered_by_entity: dict[str, set[str]] = {}
    replies_by_entity: dict[str, set[str]] = {}
    evidence_by_entity: dict[str, set[str]] = {}

    for raw in events:
        if _classification(raw.get("event_type")) != "delivered":
            continue

        occurred_at = _utc(raw.get("occurred_at"), "event.occurred_at")
        if not (start <= occurred_at < end):
            continue

        intent_id = _uuid(raw.get("intent_id"), "event.intent_id")
        entity_id = intent_entity.get(intent_id)
        if entity_id is None:
            continue

        event_id = _uuid(raw.get("id"), "event.id")

        delivered_by_entity.setdefault(entity_id, set()).add(event_id)
        evidence_by_entity.setdefault(entity_id, set()).update(
            {
                f"canonical:outbound_intents:{intent_id}",
                f"canonical:outbound_events:{event_id}",
            }
        )

    for raw in replies:
        classification = _classification(raw.get("classification"))
        if classification not in COMMERCIAL_REPLY_CLASSES:
            continue

        received_at = _utc(raw.get("received_at"), "reply.received_at")
        if not (start <= received_at < end):
            continue

        intent_id = _uuid(raw.get("intent_id"), "reply.intent_id")
        entity_id = intent_entity.get(intent_id)
        if entity_id is None:
            continue

        reply_id = _uuid(raw.get("id"), "reply.id")

        replies_by_entity.setdefault(entity_id, set()).add(reply_id)
        evidence_by_entity.setdefault(entity_id, set()).update(
            {
                f"canonical:outbound_intents:{intent_id}",
                f"canonical:outbound_replies:{reply_id}",
            }
        )

    observations: list[RevenueLeakObservation] = []

    for entity_id in sorted(delivered_by_entity):
        delivered = delivered_by_entity[entity_id]
        commercial = replies_by_entity.get(entity_id, set())

        # This observer represents only observed zero-commercial-reply
        # leakage. Positive/question/objection evidence closes this
        # particular leak condition.
        if not delivered or commercial:
            continue

        observations.append(
            RevenueLeakObservation(
                entity_id=entity_id,
                window_start=start,
                window_end=end,
                delivered_count=len(delivered),
                commercial_reply_count=0,
                evidence_refs=tuple(
                    sorted(evidence_by_entity.get(entity_id, set()))
                ),
            )
        )

    return observations
