"""Read-only Capital Allocator review API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query


class CapitalReviewRepository(Protocol):
    def recommendations(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def recommendation(self, candidate_key: str) -> Mapping[str, Any] | None:
        ...


def create_capital_router(
    repository: CapitalReviewRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/capital",
        tags=["capital-review"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "repository_available": repository is not None,
        }

    @router.get("/recommendations")
    def recommendations(
        limit: int = Query(default=100, ge=1, le=500),
    ):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="capital_review_repository_not_activated",
            )
        rows = [dict(row) for row in repository.recommendations(limit=limit)]
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/recommendations/{candidate_key}")
    def recommendation(candidate_key: str):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="capital_review_repository_not_activated",
            )
        row = repository.recommendation(candidate_key)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="capital_recommendation_not_found",
            )
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "recommendation": dict(row),
        }

    return router
