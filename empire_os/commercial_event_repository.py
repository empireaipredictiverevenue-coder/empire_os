"""Append-only commercial event repository.

Idempotency is verified by exact key lookup. Unrelated constraint failures are
never swallowed as duplicates.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.data_query import DataFilter


class CommercialEventRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def _existing(
        self,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "commercial_events",
            "id,idempotency_key",
            filters=(DataFilter.eq("idempotency_key", idempotency_key),),
            limit=1,
        )
        return dict(rows[0]) if rows else None

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

        if self._existing(idempotency_key) is not None:
            return False

        try:
            rows = self._gateway.insert(
                "commercial_events",
                dict(event),
                return_repr=True,
            )
        except Exception:
            if self._existing(idempotency_key) is not None:
                return False
            raise

        if not rows:
            raise RuntimeError("commercial event insert returned no row")
        return True

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
