"""Repository contract for canonical Search Intelligence reads.

This module defines the API-facing contract only. It does not configure
production credentials and does not provide a synthetic runtime fallback.
"""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class SearchRepository(Protocol):
    """Read-only repository surface consumed by the Search Intelligence API."""

    def summary(self) -> Mapping[str, Any]:
        ...

    def pages(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def opportunities(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def indexation(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def decay(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def cannibalisation(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def alerts(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def revenue(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...


def bounded_limit(value: int, *, maximum: int = 500) -> int:
    return max(1, min(int(value), maximum))


def collection_payload(
    items: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> dict[str, Any]:
    rows = [dict(item) for item in items]
    return {
        "available": True,
        "source": "canonical_search_repository",
        "count": len(rows),
        "limit": bounded_limit(limit),
        "items": rows,
    }
