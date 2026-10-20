"""Finite, SHA-pinned website release routes for the existing public gateway.

The owner gateway must explicitly mount this router before its legacy /brand
and /art handlers. No new process, general filesystem browser or publication
authority is introduced. Assets only resolve after the reviewed static export
has been independently installed byte-for-byte.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse


# These pages have no purchase, buyer-call or outbound authority. Preview
# intelligence articles and calculators remain noindex/nofollow by design.
INSIGHT_PAGES: dict[str, str] = {
    "ai-readiness-assessment-uk": "insights/ai-readiness-assessment-uk.html",
    "revenue-opportunity-assessment": "insights/revenue-opportunity-assessment.html",
    "us-roofing-lead-qualification": "insights/us-roofing-lead-qualification.html",
    "us-solar-lead-appointment-qualification": "insights/us-solar-lead-appointment-qualification.html",
}

# Finite set of asset paths derived from the reviewed flagship export.
# Every entry is bound to the exact approved original bytes; an edited or
# replaced file becomes a 404 rather than serving unreviewed content.
# Values: SHA-256 hex, exact response content type, size ceiling.
PINNED_ASSETS: dict[str, tuple[str, str, int]] = {
    # Exact SHA-pinned asset required by the released ASTRA homepage theme.
    "brand/empire-orbital-a-reference-mark.webp": (
        "4dc229208a44d8b8c1d076cc3f55d68255ea004b2aba4cd1bd78d331831c81aa",
        "image/webp", 10_000,
    ),
    "brand/empire-ai-founder-reference-orbital-a-transparent.webp": (
        "20f2b586e69307002e10301395fc8a7f0e768311d5b6a22a9143eab9372c6ab7", "image/webp", 30_000
    ),
    "art/empire-atrium.webp": (
        "64ffb6a8716f712d4a0a831ff8f300124f47360ce20e0500cc41f249617a403d", "image/webp", 600_000
    ),
    "art/earth-detail-v2.webp": (
        "23f26c12f9cdf0b2333283870f8a303a0ade1f98161c2eb60e25692353c68b94", "image/webp", 600_000
    ),
    "art/earth-horizon.webp": (
        "0c515931be502a6ee016360775e52eea40dff36c30da5e10c17d7926f18a9e72", "image/webp", 400_000
    ),
    "art/earth/day.jpg": (
        "767ee1dc6eb3802699bfccf6f264880f8acd0b80de3191cd24984fe279b07b7c", "image/jpeg", 650_000
    ),
    "art/earth/night.jpg": (
        "c16fd1bc096ab91a5c5265c6ff9847c43f489f2e2ee790ccdbcbd03251cf3a5a", "image/jpeg", 400_000
    ),
    "art/earth/clouds.jpg": (
        "fffd7f68d41b37274822150e54a6ef605af1d3ec35624d9f628c3b896bfa42ed", "image/jpeg", 1_200_000
    ),
    "art/earth/credits.html": (
        "1f1a6d9a17f22d99599a646c5bc4030e8f1350a3f8efa2f2b44a87ab01d48c4a", "text/html", 10_000
    ),
    "art/sectors/roofing-work-original.jpg": (
        "21c83d7e3881718b82bc6e32b90ff743892a9df98f10268652737872b7b0dcb0", "image/jpeg", 500_000
    ),
    "art/sectors/solar-sunset-original.jpg": (
        "1694ad7240672f5aaacc387978ac2ce3a182f4edae95b12c221241ef14857e9e", "image/jpeg", 400_000
    ),
}


def _regular_inside(root: Path, relative: str) -> Path | None:
    """No symlinks, traversal, empty objects or arbitrary filesystem paths."""
    if (not relative or relative.startswith("/") or ".." in relative.split("/")
            or root.is_symlink() or not root.is_dir()):
        return None
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink():
            return None
        current = current.parent
    return path if path.is_file() and path.stat().st_size > 0 else None


def reviewed_asset_path(route: str, site_out: Path) -> tuple[Path, str] | None:
    key = route.lstrip("/")
    spec = PINNED_ASSETS.get(key)
    if spec is None:
        return None
    path = _regular_inside(site_out, key)
    if path is None or path.stat().st_size > spec[2]:
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != spec[0]:
        return None
    return path, spec[1]


def create_flagship_static_release_router(site_out: Path) -> APIRouter:
    """Attach only finite reviewed routes to the already-existing gateway."""
    router = APIRouter(include_in_schema=False)

    @router.api_route("/about", methods=["GET", "HEAD"])
    async def about():
        path = _regular_inside(site_out, "about.html")
        if path is None:
            return JSONResponse({"error": "about_not_published"}, status_code=404)
        return FileResponse(path, media_type="text/html", headers={"Cache-Control": "no-store"})

    @router.api_route("/insights/{slug}", methods=["GET", "HEAD"])
    async def insight(slug: str):
        relative = INSIGHT_PAGES.get(slug)
        path = _regular_inside(site_out, relative) if relative else None
        if path is None:
            return JSONResponse(
                {"error": "insight_not_published"}, status_code=404,
                headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
            )
        return FileResponse(
            path, media_type="text/html",
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
        )

    # Keep legacy /brand/{asset} routes intact; only the exact new filename
    # is claimed here, avoiding accidental interception of other logos.
    @router.api_route(
        "/brand/empire-ai-founder-reference-orbital-a-transparent.webp",
        methods=["GET", "HEAD"],
    )
    async def approved_brand():
        return _asset_response("brand/empire-ai-founder-reference-orbital-a-transparent.webp")

    @router.api_route(
        "/brand/empire-orbital-a-reference-mark.webp", methods=["GET", "HEAD"],
    )
    async def cinematic_homepage_exact_brand():
        return _asset_response("brand/empire-orbital-a-reference-mark.webp")

    @router.api_route("/art/{asset_name}", methods=["GET", "HEAD"])
    async def top_art(asset_name: str):
        return _asset_response("art/" + asset_name)

    @router.api_route("/art/earth/{asset_name}", methods=["GET", "HEAD"])
    async def earth_art(asset_name: str):
        return _asset_response("art/earth/" + asset_name)

    @router.api_route("/art/sectors/{asset_name}", methods=["GET", "HEAD"])
    async def sector_art(asset_name: str):
        return _asset_response("art/sectors/" + asset_name)

    def _asset_response(relative: str):
        item = reviewed_asset_path("/" + relative, site_out)
        if item is None:
            return JSONResponse(
                {"error": "reviewed_asset_unavailable"}, status_code=404,
                headers={"Cache-Control": "no-store"},
            )
        path, mime = item
        extra = {"X-Robots-Tag": "noindex, follow"} if relative.endswith("/credits.html") else {}
        return FileResponse(
            path, media_type=mime,
            headers={"Cache-Control": "public, max-age=86400", **extra},
        )

    return router
