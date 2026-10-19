#!/usr/bin/env python3
"""Validate visible, server-rendered Empire Analytics markup after a private release.

Unlike a raw HTML substring search, HTMLParser respects nested headings and
HTML entities. Scripts/Next hydration JSON do not count as visible evidence.
Only a bounded HTML document is read; errors never print private page contents.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import sys

MAX_HTML_BYTES = 512 * 1024
EXPECTED_BRAND_FILE = "empire-ai-official-brand-logo-lockup.png"


class AnalyticsRenderHeld(ValueError):
    pass


def normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


class AnalyticsHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.h1_depth = 0
        self.h1_pieces: list[str] = []
        self.visible_pieces: list[str] = []
        self.logo = False
        self.robots: list[str] = []
        self.sections: set[str] = set()
        self.clicks_svg = False
        self.evidence_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.hidden_depth += 1
        if tag == "h1":
            self.h1_depth += 1
        if tag == "meta" and values.get("name", "").lower() == "robots":
            self.robots.append(values.get("content") or "")
        if tag == "img" and values.get("alt") == "Empire AI Predictive Revenue":
            source = (values.get("src") or "") + " " + (values.get("srcset") or "")
            self.logo = EXPECTED_BRAND_FILE in source and "brand" in source
        if tag == "section" and values.get("aria-label"):
            self.sections.add(values["aria-label"])
        if tag == "svg" and "reported clicks" in (values.get("aria-label") or "").lower():
            self.clicks_svg = True
        if tag == "a" and values.get("href") == "/department/evidence":
            self.evidence_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self.hidden_depth = max(0, self.hidden_depth - 1)
        if tag == "h1":
            self.h1_depth = max(0, self.h1_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.hidden_depth:
            return
        self.visible_pieces.append(data)
        if self.h1_depth:
            self.h1_pieces.append(data)


def verify_html(body: bytes) -> None:
    if not isinstance(body, bytes) or not body or len(body) > MAX_HTML_BYTES:
        raise AnalyticsRenderHeld("PRIVATE_HTML_SIZE_OR_TYPE_INVALID")
    try:
        source = body.decode("utf-8", errors="strict")
        parser = AnalyticsHTML()
        parser.feed(source)
        parser.close()
    except (UnicodeError, ValueError):
        raise AnalyticsRenderHeld("PRIVATE_HTML_UNPARSABLE") from None
    heading = normalized(" ".join(parser.h1_pieces))
    if heading != "analytics command centre":
        raise AnalyticsRenderHeld("BRANDED_ANALYTICS_HEADING_NOT_VISIBLE")
    text = normalized(" ".join(parser.visible_pieces))
    for marker in (
        "observed organic search trend",
        "observed daily impressions",
        "observed daily clicks",
        "visitors & sessions",
        "attributed revenue",
        "not connected",
        "source availability",
        "google search console",
    ):
        if marker not in text:
            raise AnalyticsRenderHeld("PRIVATE_ANALYTICS_REQUIRED_EVIDENCE_NOT_RENDERED")
    if "analytics data unavailable" in text or "department evidence unavailable" in text:
        raise AnalyticsRenderHeld("PRIVATE_ANALYTICS_HELD_FALLBACK_RENDERED")
    if not parser.logo:
        raise AnalyticsRenderHeld("EMPIRE_OFFICIAL_BRAND_ASSET_NOT_RENDERED")
    if "First-party daily search trend" not in parser.sections:
        raise AnalyticsRenderHeld("GSC_SOURCE_CHART_SECTION_NOT_RENDERED")
    if not parser.clicks_svg or not parser.evidence_link:
        raise AnalyticsRenderHeld("CLICK_TREND_OR_EVIDENCE_LINK_MISSING")
    if not any("noindex" in x.lower() and "nofollow" in x.lower() for x in parser.robots):
        raise AnalyticsRenderHeld("NOINDEX_NOFOLLOW_METADATA_MISSING")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-stdin", required=True, action="store_true")
    args = parser.parse_args(argv)
    assert args.verify_stdin
    body = sys.stdin.buffer.read(MAX_HTML_BYTES + 1)
    try:
        verify_html(body)
    except AnalyticsRenderHeld as exc:
        print("EMPIRE_ANALYTICS_RENDER_HELD:" + str(exc), file=sys.stderr)
        return 2
    print("EMPIRE_ANALYTICS_BRANDED_RENDER_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
