"""Canonical URL analysis and recommendation."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import CanonicalRecommendation

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"gclid", "fbclid", "msclkid"}


def _drop_tracking(query: str) -> str:
    kept = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        low = key.lower()
        if low in _TRACKING_KEYS or any(low.startswith(p) for p in _TRACKING_PREFIXES):
            continue
        kept.append((key, value))
    return urlencode(kept, doseq=True)


def evaluate_canonical(url: str) -> CanonicalRecommendation:
    if not url or "://" not in url:
        raise ValueError("absolute URL required")

    parts = urlsplit(url)
    issues: list[str] = []
    actions: list[str] = []

    scheme = parts.scheme.lower()
    if scheme != "https":
        scheme = "https"
        issues.append("http_https_inconsistency")
        actions.append("prefer_https")

    host = (parts.hostname or "").lower()
    port = parts.port
    if host.startswith("www."):
        host = host[4:]
        issues.append("www_non_www_inconsistency")
        actions.append("choose_non_www_canonical")

    netloc = host
    if port and not (scheme == "https" and port == 443):
        netloc = f"{host}:{port}"

    path = parts.path or "/"
    lowered = path.lower()
    if path != lowered:
        issues.append("route_case_inconsistency")
        actions.append("review_lowercase_route_canonical")
        path = lowered

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        issues.append("trailing_slash_inconsistency")
        actions.append("prefer_no_trailing_slash")

    query = _drop_tracking(parts.query)
    if query != parts.query:
        issues.append("tracking_parameter_variant")
        actions.append("exclude_tracking_parameters_from_canonical")
    if query:
        issues.append("query_parameter_variant")
        actions.append("review_parameter_canonical")

    recommended = urlunsplit((scheme, netloc, path, query, ""))
    return CanonicalRecommendation(
        input_url=url,
        recommended_url=recommended,
        issues=tuple(dict.fromkeys(issues)),
        recommended_actions=tuple(dict.fromkeys(actions)),
        requires_review=bool(issues),
    )
