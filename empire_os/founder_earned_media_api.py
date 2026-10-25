"""Founder-only, disabled-by-default review of existing earned media work.

This deliberately mounts only into the pre-existing loopback Founder service.
No production enablement, CRM DB access or contact/publish/quote endpoints.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from empire_os.earned_media_advisory_bridge import review


DEFAULT_REPO = Path("/srv/empire_os")
DEFAULT_PR_SOURCE = Path("/home/ubuntu/empire_agents/empire_pr_consultancy_20261011")


def create_founder_earned_media_router(
    *,
    repo_root: Path | None = None,
    pr_root: Path | None = None,
    distribution_root: Path | None = None,
    enabled: bool | None = None,
) -> APIRouter:
    """Mount private review GET only; off until founder access is independently checked."""
    active = (os.getenv("EMPIRE_EARNED_MEDIA_FOUNDER_READ_ENABLED") == "1"
              if enabled is None else enabled)
    root = repo_root if repo_root is not None else DEFAULT_REPO
    press = pr_root if pr_root is not None else DEFAULT_PR_SOURCE
    distribution = distribution_root if distribution_root is not None else DEFAULT_REPO
    router = APIRouter(prefix="/v1/founder-earned-media", tags=["founder-earned-media"])

    @router.get("/review")
    def get_earned_media_review():
        if not active:
            raise HTTPException(status_code=404, detail="not_enabled")
        try:
            packet = review(root, pr_root=press, distribution_root=distribution)
        except (OSError, ValueError, TypeError):
            # Avoid leaking private paths, file bodies or server internals.
            raise HTTPException(status_code=503, detail="source_review_held")
        return {
            **packet,
            "read_only": True,
            "crm_reconciliation_state": "NOT_STARTED_NO_CANONICAL_TENANT_OR_COMPANY_EVIDENCE",
            "mailbox_freshness": "HISTORICAL_SENT_RECEIPTS_NOT_LIVE_GMAIL",
            "deployment_authorized": False,
            "private_access_verification_required": True,
        }

    return router
