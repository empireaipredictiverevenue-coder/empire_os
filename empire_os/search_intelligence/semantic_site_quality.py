"""Evidence-led commercial site quality inspection for existing Empire AI URLs.

Pure read-only HTML analysis: observes visible terms, accessible CTA routes,
and form presence. Does NOT submit forms, measure ranking, claim working
conversion delivery, or award subjective SEO quality scores.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from typing import Any, Mapping, Sequence
import re

from .first_party_semantic_corpus import PageSpec, page_record


class _VisiblePage(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.visible: list[str] = []
        self.h2: list[str] = []
        self._heading: list[str] | None = None
        self.links: list[tuple[str, str]] = []
        self.current_link: list[str] | None = None
        self.current_link_url: str | None = None
        self.forms = 0
        self.inputs: list[dict[str, Any]] = []
        self.submit_buttons = 0
        self._button_type: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag in {"script", "style", "svg", "noscript", "template"}:
            self.skip += 1
        if tag == "h2" and self.skip == 0:
            self._heading = []
        if tag == "a" and self.skip == 0:
            self.current_link_url = str(a.get("href") or "")
            self.current_link = []
        if tag == "form":
            self.forms += 1
        if tag == "input":
            self.inputs.append({
                "type": str(a.get("type") or "text").lower(),
                "required": "required" in a,
            })
        if tag == "button":
            self._button_type = str(a.get("type") or "submit").lower()

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._heading is not None:
            title = " ".join(" ".join(self._heading).split())
            if title:
                self.h2.append(title)
            self._heading = None
        if tag == "a" and self.current_link is not None:
            self.links.append((
                self.current_link_url or "",
                " ".join(" ".join(self.current_link).split()),
            ))
            self.current_link = None
            self.current_link_url = None
        if tag == "button" and self._button_type is not None:
            if self._button_type == "submit":
                self.submit_buttons += 1
            self._button_type = None
        if tag in {"script", "style", "svg", "noscript", "template"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        words = data.strip()
        if not words:
            return
        self.visible.append(words)
        if self._heading is not None:
            self._heading.append(words)
        if self.current_link is not None:
            self.current_link.append(words)


def _path_for_owned_link(base_url: str, link: str) -> str | None:
    try:
        source = urlsplit(base_url)
        dest = urlsplit(urljoin(base_url, link))
    except ValueError:
        return None
    if (source.hostname != "empire-ai.co.uk"
            or dest.hostname not in {"empire-ai.co.uk", "www.empire-ai.co.uk"}
            or dest.scheme not in {"https", "http"}
            or dest.username or dest.password):
        return None
    return dest.path or "/"


def inspect_owned_commercial_page(
    spec: PageSpec,
    *,
    html: str,
    http_status: int,
) -> dict[str, Any]:
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise ValueError("bounded page HTML required")
    source = page_record(spec, html=html, http_status=http_status)
    parser = _VisiblePage()
    parser.feed(html)
    text = " ".join(parser.visible)
    own_links = []
    for url, label in parser.links:
        path = _path_for_owned_link(spec.url, url)
        if path:
            own_links.append({"path": path, "anchor_label": label[:100]})
    routes = {row["path"] for row in own_links}
    phrases = {
        "heat_pump": bool(re.search(r"\bheat pumps?\b", text, re.I)),
        "photovoltaic": bool(re.search(r"\bphotovoltaic\b", text, re.I)),
        "quote_or_proposal": bool(re.search(r"\b(?:quote|proposal|assessment)\b", text, re.I)),
    }
    opportunities = []
    if not source["eligible_for_local_topic_review"]:
        opportunities.append({
            "severity": "high", "action": "VERIFY_HTTP_CANONICAL_AND_ROBOTS",
            "reason": "page did not satisfy observed metadata eligibility",
        })
    if "/commercial" not in routes:
        opportunities.append({
            "severity": "medium", "action": "REVIEW_EXPLICIT_PROPOSAL_ROUTE",
            "reason": "no observed owned /commercial anchor in static HTML",
        })
    if spec.product_key == "hvac" and not phrases["heat_pump"]:
        opportunities.append({
            "severity": "medium",
            "action": "EDITORIAL_REVIEW_HVAC_HEAT_PUMP_CONTEXT",
            "reason": "live visible page text does not explicitly describe heat pumps",
            "publication_authorized": False,
        })
    if spec.product_key == "solar" and not phrases["photovoltaic"]:
        opportunities.append({
            "severity": "low",
            "action": "EDITORIAL_REVIEW_SOLAR_PV_EXPLANATION",
            "reason": "visible page text omits the word photovoltaic; not a proven ranking gap",
            "publication_authorized": False,
        })
    return {
        "schema_version": "semantic_site_quality.v1",
        "url": spec.url,
        "product_key": spec.product_key,
        "source_evidence_refs": source["evidence_refs"],
        "metadata_eligible": source["eligible_for_local_topic_review"],
        "observed_http_status": http_status,
        "h1": source["h1"],
        "visible_word_count_estimate": len(text.split()),
        "visible_h2_headings": parser.h2[:50],
        "observed_internal_link_count": len(own_links),
        "observed_commercial_form_route_link": "/commercial" in routes,
        "observed_roi_assessment_route_link": (
            "/insights/revenue-opportunity-assessment" in routes
        ),
        "observed_sector_phrases": phrases,
        "editorial_review_candidates": opportunities,
        "page_engagement_measured": False,
        "google_indexing_proven": False,
        "converted_leads_proven": False,
        "site_content_modified": False,
        "execution_authority": "none",
    }


def inspect_commercial_form_html(html: str, *, http_status: int) -> dict[str, Any]:
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise ValueError("bounded form page HTML required")
    parser = _VisiblePage()
    parser.feed(html)
    required_count = sum(int(item["required"]) for item in parser.inputs)
    email_count = sum(item["type"] == "email" for item in parser.inputs)
    return {
        "schema_version": "commercial_form_presence_readonly.v1",
        "url": "https://empire-ai.co.uk/commercial",
        "http_status": http_status,
        "evidence_ref": "owned-html-sha256:" + sha256(html.encode()).hexdigest(),
        "static_form_element_count": parser.forms,
        "email_input_count": email_count,
        "required_input_count": required_count,
        "submit_button_count": parser.submit_buttons,
        "static_form_presence_observed": (
            http_status == 200 and parser.forms > 0
            and email_count > 0 and parser.submit_buttons > 0
        ),
        "submission_executed": False,
        "submission_delivery_verified": False,
        "crm_record_verified": False,
        "execution_authority": "none",
    }
