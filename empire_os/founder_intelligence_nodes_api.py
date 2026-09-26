"""Read-only Founder Intelligence Nodes API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from empire_os.founder_intelligence_nodes import (
    build_intelligence_nodes_projection,
    get_intelligence_node_projection,
)


def create_founder_intelligence_nodes_router(
    repo_root: Path | None = None,
) -> APIRouter:
    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(
        prefix="/v1/founder-intelligence-nodes",
        tags=["founder-intelligence-nodes"],
    )

    @router.get("")
    def list_nodes():
        return build_intelligence_nodes_projection(root)

    @router.get("/{node_key}")
    def get_node(node_key: str):
        row = get_intelligence_node_projection(root, node_key)
        if row is None:
            raise HTTPException(404, "intelligence node not found")
        return row

    return router
