"""OBSERVE-only robots/crawl governance recommendations."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class RobotsRecommendation:
    robots: str
    reason: str
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_BLOCK_PREFIXES = (
    "/admin", "/auth", "/dashboard", "/api", "/preview",
    "/internal-search", "/search/internal", "/tracking", "/track", "/test",
)
_PRIVATE_MARKERS = ("/campaign/private", "/private/")


def recommend_robots(
    url: str,
    *,
    is_private: bool = False,
    quality_approved: bool | None = None,
    canonical: bool | None = None,
) -> RobotsRecommendation:
    path = urlsplit(str(url or "")).path.lower() or "/"
    if is_private or any(marker in path for marker in _PRIVATE_MARKERS):
        return RobotsRecommendation("noindex,nofollow", "private_surface")
    if any(path == prefix or path.startswith(prefix + "/") for prefix in _BLOCK_PREFIXES):
        return RobotsRecommendation("noindex,nofollow", "nonpublic_system_route")
    if canonical is not True:
        return RobotsRecommendation("noindex,follow", "canonical_not_verified")
    if quality_approved is not True:
        return RobotsRecommendation("noindex,follow", "quality_not_approved")
    return RobotsRecommendation("index,follow", "eligible_public_page")
