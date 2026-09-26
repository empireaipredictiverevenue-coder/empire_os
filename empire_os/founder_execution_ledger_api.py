"""Read-only Founder API for the canonical Empire execution ledger."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from empire_os.master_execution_ledger import build_execution_ledger


DEFAULT_CHECKLIST = Path(
    "/srv/empire_os/docs/MASTER_REMAINING_CHECKLIST.md"
)


def create_founder_execution_ledger_router(
    checklist_path: Path = DEFAULT_CHECKLIST,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-execution-ledger",
        tags=["founder-execution-ledger"],
    )

    @router.get("/status")
    def status(pending_only: bool = False):
        ledger = build_execution_ledger(checklist_path)
        if pending_only:
            ledger["items"] = [
                item
                for item in ledger["items"]
                if item["status"] == "PENDING"
            ]
        ledger["read_only"] = True
        ledger["execution_authority"] = "none"
        return ledger

    return router
