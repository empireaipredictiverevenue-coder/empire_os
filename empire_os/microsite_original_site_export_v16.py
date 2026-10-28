"""Original ASTRA-owned metadata polish for one SHA-locked Chicago review asset.

Generates only private, not-yet-approved export bytes. It does not change the
V10 source preview ID, the original website gateway or owner permissions.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from typing import Any

from empire_os.microsite_original_gateway_addendum_v12 import (
    ORIGINAL_PREVIEW_SHA,
)

SOURCE_TITLE = (
    '<title><span class="hero-title-base">Chicago reroofing:</span>'
    '<span class="hero-title-accent">permits, licensing and scope checks</span>'
    ' | Empire AI Research Preview</title>'
)
REVIEWED_TITLE = (
    '<title>Chicago reroofing: permits, licensing and scope checks '
    '| Empire AI Research</title>'
)
SOURCE_H1 = (
    '<h1><span class="hero-title-base">Chicago reroofing:</span>'
    '<span class="hero-title-accent">permits, licensing and scope checks</span></h1>'
)
REVIEWED_H1 = (
    '<h1><span class="hero-title-base">Chicago reroofing:</span> '
    '<span class="hero-title-accent">permits, licensing and scope checks</span></h1>'
)
SOURCE_DESCRIPTION = (
    '<meta name="description" content="A citywide research checklist for '
    'properties under Chicago jurisdiction. Check the actual address and '
    'project before relying on permit rules. no contractor">'
)
REVIEWED_DESCRIPTION = (
    '<meta name="description" content="Chicago reroofing research: '
    'check permit eligibility, contractor licensing, and project scope '
    'against official city and state guidance.">'
)
EDITIONS = {
    SOURCE_TITLE: REVIEWED_TITLE,
    SOURCE_H1: REVIEWED_H1,
    SOURCE_DESCRIPTION: REVIEWED_DESCRIPTION,
}


class _MarkupCheck(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_depth = 0
        self.invalid_title_tags: list[str] = []
        self.meta_description = []
        self.titles = []
        self.h1 = 0
        self.script_or_form = 0
        self.img = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.title_depth += 1
        elif self.title_depth:
            self.invalid_title_tags.append(tag)
        if tag == "meta" and values.get("name") == "description":
            self.meta_description.append(values.get("content"))
        if tag == "h1":
            self.h1 += 1
        if tag in ("script", "form"):
            self.script_or_form += 1
        if tag == "img":
            self.img += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.title_depth -= 1


def prepare_chicago_original_owner_export(source: bytes) -> tuple[bytes, dict[str, Any]]:
    """Deterministic private owner-review export. Never claims rights/approval."""
    if sha256(source).hexdigest() != ORIGINAL_PREVIEW_SHA:
        raise ValueError("Exact original V10 source preview SHA is required")
    text = source.decode("utf-8")
    for old, new in EDITIONS.items():
        if text.count(old) != 1 or new in text:
            raise ValueError("Original Chicago metadata/heading has changed unexpectedly")
        text = text.replace(old, new, 1)
    if ('<meta name="robots" content="noindex,nofollow,noarchive">' not in text
            or "research-signal-strip" not in text
            or "Illustrative roofing photo · Houston, TX" not in text
            or "<script" in text.lower() or "<form" in text.lower()):
        raise ValueError("Safe-source restrictions or photographic attribution not preserved")
    qa = _MarkupCheck()
    qa.feed(text)
    if (qa.invalid_title_tags or len(qa.meta_description) != 1
            or qa.meta_description[0] != REVIEWED_DESCRIPTION.split('content="', 1)[1][:-2]
            or qa.h1 != 1 or qa.script_or_form or qa.img != 1):
        raise ValueError("Invalid HTML title, metadata, heading or page safety")
    raw = text.encode("utf-8")
    return raw, {
        "schema_version": "empire.original_website.chicago_review_export_v16",
        "candidate_state": "PRIVATE_STAGED_ONLY_NO_OWNER_APPROVAL",
        "source_preview_sha256": ORIGINAL_PREVIEW_SHA,
        "owner_reviewed_html_sha256": sha256(raw).hexdigest(),
        "owner_reviewed_html_bytes": len(raw),
        "deterministic_edits": 3,
        "valid_plain_text_title": True,
        "complete_meta_description": True,
        "visible_heading_spacing_fixed": True,
        "noindex_preserved": True,
        "original_brand_media_embedded_without_public_upload": True,
        "first_party_source_claims_unchanged": True,
        "public_url": None,
        "owner_approvals_granted": False,
        "production_writes": 0,
    }
