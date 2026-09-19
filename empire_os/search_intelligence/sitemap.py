"""Pure sitemap planning; never writes or submits a sitemap."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from .models import PageLifecycleState


_ALLOWED_STATES = {
    PageLifecycleState.APPROVED.value,
    PageLifecycleState.PUBLISHED.value,
    PageLifecycleState.INDEXABLE.value,
    PageLifecycleState.SUBMITTED.value,
    PageLifecycleState.DISCOVERED_BY_GOOGLE.value,
    PageLifecycleState.CRAWLED.value,
    PageLifecycleState.INDEXED.value,
}


def _identity(url: str) -> str:
    p = urlsplit(url.strip())
    path = p.path or "/"
    return urlunsplit(
        (p.scheme.lower(), p.netloc.lower(), path, p.query, "")
    )


def _sitemap_url(url: str) -> str:
    p = urlsplit(url.strip())
    path = p.path or "/"
    return urlunsplit(
        (p.scheme.lower(), p.netloc.lower(), path, p.query, "")
    )


def build_sitemap_plan(
    pages: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    excluded: list[dict[str, str]] = []

    for raw in pages:
        page = dict(raw)
        url = str(page.get("url") or "").strip()
        canonical = str(page.get("canonical_url") or "").strip()
        page_type = str(page.get("page_type") or "pages").strip().lower() or "pages"
        state = page.get("index_state")
        state_value = getattr(state, "value", state)
        reason = None

        if not url or not canonical:
            reason = "missing_url_or_canonical"
        elif _identity(url) != _identity(canonical):
            reason = "noncanonical_url"
        elif page.get("indexable") is not True:
            reason = "not_indexable"
        elif str(state_value or "") not in _ALLOWED_STATES:
            reason = "not_approved_index_state"

        if reason:
            excluded.append({"url": url or canonical, "reason": reason})
            continue
        groups[page_type].append(_sitemap_url(canonical))

    clean_groups = {
        key: sorted(set(urls))
        for key, urls in sorted(groups.items())
    }
    return {
        "groups": clean_groups,
        "sitemap_index": tuple(
            {"group": key, "url_count": len(urls)}
            for key, urls in clean_groups.items()
        ),
        "excluded": tuple(excluded),
        "publish_allowed": False,
        "submit_allowed": False,
    }
