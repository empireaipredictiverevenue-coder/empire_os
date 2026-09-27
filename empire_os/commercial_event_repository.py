"""Append-only commercial event repository.

Consequential event history is inserted through the Canonical Data Gateway.
Idempotent appends use untargeted conflict-ignore so partial unique indexes
(such as commercial_events.idempotency_key WHERE NOT NULL) remain enforceable.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.canonical_data_gateway import CanonicalDataGateway


class CommercialEventRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def append_idempotent(
        self,
        event: Mapping[str, Any],
    ) -> bool:
        event_type = str(event.get("event_type") or "").strip()
        actor = str(event.get("actor") or "").strip()
        idempotency_key = str(event.get("idempotency_key") or "").strip()

        if not event_type:
            raise ValueError("commercial event_type is required")
        if not actor:
            raise ValueError("commercial event actor is required")
        if not idempotency_key:
            raise ValueError("commercial event idempotency_key is required")

        rows = self._gateway.insert_ignore_conflicts(
            "commercial_events",
            dict(event),
            return_repr=True,
        )
        # PostgreSQL/PostgREST conflict-ignore returns no representation for an
        # existing idempotency key. Either outcome is successful/idempotent.
        return bool(rows)

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "append_only": True,
            "idempotent": True,
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
