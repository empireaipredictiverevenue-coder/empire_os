"""Strict review-only audit of the UK roofing static HTML export.

This never changes content, publishes routes, opens affiliate links, or collects
visitor data. The report is not buyer approval or a launch activation receipt.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

EXPORT = Path("apps/empire-public-site/out/uk/roofing.html")
ALLOWED_ANCHORS = ("#roofing-checklist", "#roof-types")
MAX_BYTES = 180_000


class _MarkupAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str | None] = []
        self.scripts: list[str | None] = []
        self.images: list[str | None] = []
        self.robots: list[str | None] = []
        self.forms = 0
        self.iframes = 0
        self.buttons: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "a":
            self.links.append(a.get("href"))
        elif tag == "form":
            self.forms += 1
        elif tag == "iframe":
            self.iframes += 1
        elif tag == "script":
            self.scripts.append(a.get("src"))
        elif tag == "img":
            self.images.append(a.get("src"))
        elif tag == "button":
            self.buttons.append(a)
        elif tag == "meta" and a.get("name", "").lower() == "robots":
            self.robots.append(a.get("content"))


def audit_html_bytes(payload: bytes) -> dict:
    errors: list[str] = []
    if len(payload) > MAX_BYTES:
        errors.append("EXPORT_TOO_LARGE")
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError:
        source = ""
        errors.append("INVALID_UTF8")
    markup = _MarkupAudit()
    markup.feed(source)
    if markup.links != list(ALLOWED_ANCHORS):
        errors.append("UNAPPROVED_NAVIGATION")
    if markup.forms or markup.iframes:
        errors.append("ACTIVE_CONVERSION_SURFACE")
    if len(markup.buttons) != 1 or not all(
        "disabled" in b and b.get("aria-disabled") == "true"
        for b in markup.buttons
    ):
        errors.append("QUOTE_CONTROL_NOT_DISABLED")
    if (
        len(markup.robots) != 1
        or "noindex" not in (markup.robots[0] or "").lower()
        or "nofollow" not in (markup.robots[0] or "").lower()
    ):
        errors.append("INDEXING_NOT_WITHHELD")
    if any(src and (src.startswith("//") or not src.startswith("/")) for src in markup.scripts):
        errors.append("REMOTE_SCRIPT")
    if markup.images != ["/brand/empire-mark.svg"]:
        errors.append("UNAPPROVED_IMAGE_SOURCE")
    disclosure = source.find("Ad · planned partner link (inactive)")
    commission_notice = source.find("Empire AI may earn")
    inactive_notice = source.find("No affiliate link is currently active")
    disabled_action = source.find("Quote enquiry unavailable during affiliate review")
    if not (0 <= disclosure < commission_notice < inactive_notice < disabled_action):
        errors.append("INACTIVE_AFFILIATE_DISCLOSURE_MISSING_OR_LATE")
    if re.search(r"(?i)tel:|click\.myjobquote|affiliate_id|lead_form|tracking_number|<input\b", source):
        errors.append("TRACKING_OR_LEAD_CAPTURE")
    return {
        "schema_version": "empire.myjobquote.uk_roofing_export_safety.v1",
        "mode": "OBSERVE",
        "execution_authority": "NONE",
        "result": "PASS" if not errors else "FAIL_CLOSED",
        "errors": errors,
        "export_sha256": hashlib.sha256(payload).hexdigest(),
        "anchors": markup.links,
        "form_count": markup.forms,
        "iframe_count": markup.iframes,
        "script_count": len(markup.scripts),
        "external_script_count": sum(bool(s and (s.startswith("//") or not s.startswith("/"))) for s in markup.scripts),
        "button_disabled_verified": not any(e == "QUOTE_CONTROL_NOT_DISABLED" for e in errors),
        "traffic_authorized": False,
        "affiliate_url_authorized": False,
        "buyer_terms_approved": False,
    }


def audit(path: Path = EXPORT) -> dict:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise OSError("untrusted export path")
        return audit_html_bytes(path.read_bytes())
    except (OSError, ValueError):
        return {
            "schema_version": "empire.myjobquote.uk_roofing_export_safety.v1",
            "mode": "OBSERVE",
            "execution_authority": "NONE",
            "result": "FAIL_CLOSED",
            "errors": ["MISSING_OR_UNTRUSTED_EXPORT"],
            "traffic_authorized": False,
            "affiliate_url_authorized": False,
            "buyer_terms_approved": False,
        }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
