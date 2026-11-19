"""Bounded public-web recovery providers for Empire Search Fabric.

These providers exist only when the normal Search Fabric providers return
no usable evidence.

Rules:
- ordinary public HTTP only;
- no CAPTCHA bypass;
- no account/session impersonation;
- one request per provider per query;
- conservative parsing;
- results still pass Search Fabric's existing lexical quality gate;
- search evidence never establishes commercial identity by itself.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any


DEFAULT_TIMEOUT = 6.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124 Safari/537.36"
)

_PROVIDER_HOSTS = {
    "search.brave.com",
    "www.google.com",
    "google.com",
}


def _clean(value: Any) -> str:
    return " ".join(
        html.unescape(
            str(value or "")
        ).split()
    )


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )
        self._href: str | None = None
        self._text: list[str] = []
        self.anchors: list[
            tuple[str, str]
        ] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[
            tuple[str, str | None]
        ],
    ) -> None:
        if tag.lower() != "a":
            return

        values = dict(attrs)
        href = values.get("href")

        if not href:
            return

        self._href = href
        self._text = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag.lower() != "a"
            or self._href is None
        ):
            return

        title = _clean(
            " ".join(self._text)
        )

        if title:
            self.anchors.append(
                (
                    self._href,
                    title,
                )
            )

        self._href = None
        self._text = []


def _unwrap_url(
    href: str,
    *,
    provider: str,
) -> str:
    href = html.unescape(
        str(href or "")
    ).strip()

    if not href:
        return ""

    if href.startswith("//"):
        href = "https:" + href

    if href.startswith("/"):
        if provider == "google_html":
            parsed = urllib.parse.urlparse(
                href
            )

            params = urllib.parse.parse_qs(
                parsed.query
            )

            for key in (
                "q",
                "url",
            ):
                candidate = (
                    params.get(key)
                    or [""]
                )[0]

                if candidate.startswith(
                    ("http://", "https://")
                ):
                    href = candidate
                    break
            else:
                return ""
        else:
            return ""

    try:
        parsed = urllib.parse.urlparse(
            href
        )
    except ValueError:
        return ""

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return ""

    host = parsed.netloc.lower()

    if host.startswith("www."):
        normalized_host = host[4:]
    else:
        normalized_host = host

    if (
        host in _PROVIDER_HOSTS
        or normalized_host
        in {
            "search.brave.com",
            "google.com",
        }
    ):
        # Some search engines wrap external URLs in query parameters.
        params = urllib.parse.parse_qs(
            parsed.query
        )

        for key in (
            "url",
            "q",
            "target",
            "u",
        ):
            candidate = (
                params.get(key)
                or [""]
            )[0]

            if candidate.startswith(
                ("http://", "https://")
            ):
                return candidate

        return ""

    return href


class _BraveResultCollector(HTMLParser):
    """Collect only Brave's primary web-result anchors."""

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )
        self._href: str | None = None
        self._fallback_text: list[str] = []
        self._result_title: str = ""
        self.results: list[
            tuple[str, str]
        ] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[
            tuple[str, str | None]
        ],
    ) -> None:
        values = dict(attrs)

        if tag.lower() == "a":
            classes = set(
                str(
                    values.get("class")
                    or ""
                ).split()
            )

            href = values.get("href")

            # Live Brave SERP main-result links use the l1 class.
            # Video clusters, thumbnails, tabs and navigation do not.
            if (
                href
                and "l1" in classes
            ):
                self._href = href
                self._fallback_text = []
                self._result_title = ""

            return

        if (
            self._href is not None
            and tag.lower() == "div"
        ):
            classes = set(
                str(
                    values.get("class")
                    or ""
                ).split()
            )

            if (
                "search-snippet-title"
                in classes
            ):
                title = _clean(
                    values.get("title")
                )

                if title:
                    self._result_title = title

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._href is not None:
            self._fallback_text.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag.lower() != "a"
            or self._href is None
        ):
            return

        title = (
            self._result_title
            or _clean(
                " ".join(
                    self._fallback_text
                )
            )
        )

        if title:
            self.results.append(
                (
                    self._href,
                    title,
                )
            )

        self._href = None
        self._fallback_text = []
        self._result_title = ""


def parse_public_search_html(
    page: str,
    *,
    provider: str,
    limit: int = 40,
) -> list[dict[str, Any]]:
    lowered = page.lower()

    if provider == "brave_web":
        # Brave's production HTML contains incidental strings such as
        # "captcha" and "blocked" in scripts/assets even on a healthy SERP.
        # Structural web-result evidence therefore outranks those incidental
        # strings. A genuine challenge without result structure still fails
        # closed.
        has_web_results = (
            'data-type="web"' in lowered
            and "search-snippet-title"
            in lowered
        )

        if not has_web_results:
            challenge_markers = (
                "verify you are human",
                "unusual traffic",
                "challenge-form",
                "captcha-container",
            )

            if any(
                marker in lowered
                for marker in challenge_markers
            ):
                return []

        collector = (
            _BraveResultCollector()
        )

        try:
            collector.feed(page)
        except Exception:
            return []

        anchors = collector.results

    else:
        # Google currently returns an HTTP-200 access/help shell from this
        # server. Treat it as unavailable rather than interpreting navigation
        # or feedback links as search evidence.
        challenge_markers = (
            "unusual traffic",
            "verify you are human",
            "automated queries",
            "our systems have detected",
            "having trouble accessing google search",
        )

        if any(
            marker in lowered
            for marker in challenge_markers
        ):
            return []

        collector = _AnchorCollector()

        try:
            collector.feed(page)
        except Exception:
            return []

        anchors = collector.anchors

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for href, title in anchors:
        url = _unwrap_url(
            href,
            provider=provider,
        )

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        title = _clean(title)

        if len(title) < 3:
            continue

        rows.append({
            "title": title,
            "link": url,
            "snippet": "",
            "position":
                len(rows) + 1,
            "engine": provider,
        })

        if len(rows) >= limit:
            break

    return rows


def _fetch(
    url: str,
    *,
    timeout: float,
) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language":
                "en-GB,en;q=0.9",
        },
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        status = int(
            getattr(
                response,
                "status",
                200,
            )
            or 200
        )

        if status != 200:
            return ""

        raw = response.read(
            1_500_000
        )

    return raw.decode(
        "utf-8",
        errors="replace",
    )


class PublicSearchRows(list):
    """List-compatible provider evidence with operational status.

    Healthy provider response with zero relevant matches is not an outage.
    Avoid synthesising result rows solely to reset the circuit breaker.
    """
    def __init__(self, rows, *, provider_available: bool):
        super().__init__(rows)
        self.provider_available = bool(provider_available)


def search_public_web(
    query: str,
    *,
    num: int = 10,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Return bounded discovery rows from reachable public search pages."""

    providers = (
        # Reuse the existing Bing HTML parser already shipped by Search Fabric.
        # Brave currently responds 429 on the server; Bing is a bounded,
        # no-key public recovery source. One request per provider.
        (
            "bing_html",
            "https://www.bing.com/search?"
            + urllib.parse.urlencode({
                "q": query,
                "count": min(max(int(num), 1), 10),
            }),
        ),
        (
            "brave_web",
            "https://search.brave.com/search?"
            + urllib.parse.urlencode({
                "q": query,
                "source": "web",
            }),
        ),
        (
            "google_html",
            "https://www.google.com/search?"
            + urllib.parse.urlencode({
                "q": query,
                "num": min(
                    max(int(num), 1),
                    10,
                ),
                "hl": "en",
                "filter": "0",
            }),
        ),
    )

    rows: list[dict[str, Any]] = []
    provider_available = False

    for provider, url in providers:
        try:
            page = _fetch(
                url,
                timeout=timeout,
            )
        except Exception:
            continue

        if not page:
            continue

        if provider == "bing_html":
            # Single owned parser, not a second scraping implementation.
            # An access shell without organic blocks returns no rows.
            from .search import _parse_bing_html
            parsed = _parse_bing_html(page)[:max(20, min(int(num) * 4, 40))]
            parsed = [
                {**row, "engine": "bing_html"}
                for row in parsed
                if isinstance(row, dict)
            ]
            # Parsed organic rows prove that the search provider responded.
            # A clearly rendered Bing no-results block is also operational.
            # An unknown access/help shell is NOT provider evidence.
            lowered = page.lower()
            if parsed or ('id="b_results"' in lowered and
                          ('class="b_no"' in lowered or 'b_no' in lowered)):
                provider_available = True
        else:
            parsed = parse_public_search_html(
                page,
                provider=provider,
                limit=max(
                    20,
                    min(
                        int(num) * 4,
                        40,
                    ),
                ),
            )

        if parsed:
            provider_available = True
            rows.extend(parsed)
            # A usable owned-provider response is enough for one bounded
            # recovery attempt. Avoid unnecessary requests to rate-limited
            # alternative endpoints.
            if provider == "bing_html":
                break

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in rows:
        url = str(
            row.get("link")
            or ""
        )

        if not url or url in seen:
            continue

        seen.add(url)
        unique.append(row)

    return PublicSearchRows(unique, provider_available=provider_available)
