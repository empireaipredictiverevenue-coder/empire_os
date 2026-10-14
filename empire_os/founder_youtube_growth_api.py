"""Read-only YouTube Growth and optional funnel views for Founder loopback API.

The production growth route deliberately exposes only aggregate YouTube
Analytics. Funnel and campaign readers require a separate router registration.
"""
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from empire_os.media_youtube_growth_command_centre import load_youtube_growth_snapshot


PREFIX = "/v1/founder-dashboard"


def create_founder_youtube_growth_router(repo_root: Path | None = None) -> APIRouter:
    """Minimal production surface: one GET route, no campaign or CRM readers."""
    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(prefix=PREFIX, tags=["founder-dashboard"])

    @router.get("/youtube-growth")
    def youtube_growth():
        return load_youtube_growth_snapshot(root)

    return router


def create_founder_youtube_related_router(repo_root: Path | None = None) -> APIRouter:
    """Separately mountable read-only funnel surface; not part of Growth release."""
    from empire_os.media_youtube_landing_ingress import read_landing_aggregate
    from empire_os.media_youtube_canonical_funnel import load_youtube_enquiry_cohort_snapshot

    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(prefix=PREFIX, tags=["founder-dashboard"])

    @router.get("/youtube-enquiry-cohort")
    def youtube_enquiry_cohort():
        # Aggregate attested reader only; no personal CRM row fetch.
        return load_youtube_enquiry_cohort_snapshot(root)

    @router.get("/youtube-campaign-landings")
    def youtube_campaign_landings():
        # Intended only for the private Founder loopback service.
        path = root / "runtime/media_os/youtube_private_landing/landings.sqlite"
        return read_landing_aggregate(ledger_path=path)

    return router
