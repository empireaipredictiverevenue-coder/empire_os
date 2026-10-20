"""Scrapling selector-only parsing of an already permitted, fetched homepage.

The fetcher remains the sole network authority. This adapter makes *zero*
requests and emits only DOM coverage, not raw content, contacts or leads.
No stealth, browser, auto-match persistence, or CAPTCHA bypass is used.
"""
from __future__ import annotations

from hashlib import sha256
from importlib.metadata import version
from typing import Any

SCHEMA = "empire.a2a.scrapling_approved_homepage_extraction.v1"


def parse_existing_html(html: bytes, *, source_url: str) -> dict[str, Any]:
    if not isinstance(html, bytes) or not 0 < len(html) <= 400_000:
        raise ValueError("INVALID_BOUNDED_FIRST_PARTY_DOCUMENT")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("UNAPPROVED_SOURCE_URL")
    # No fetchers imported; only the existing offline parser is allowed.
    from scrapling.parser import Selector

    page = Selector(html.decode("utf-8", "replace"), url=source_url)
    titles = page.css("title::text")
    headings = page.css("h1::text")[:20]
    descriptions = page.css('meta[name="description"]::attr(content)')[:3]
    structured = page.css('script[type="application/ld+json"]')[:12]
    # Limit public structural counts; omit raw DOM text and any person/company
    # data until the canonical Buyer Scout has its own identity review.
    return {
        "schema_version": SCHEMA,
        "parser": "scrapling.parser.Selector",
        "scrapling_version": version("scrapling"),
        "document_sha256": sha256(html).hexdigest(),
        "site_url": source_url,
        "public_page_title_observed": bool(titles),
        "public_h1_count_bounded": len(headings),
        "public_meta_description_observed": bool(descriptions),
        "json_ld_blocks_seen_bounded": len(structured),
        "raw_page_or_private_contacts_exported": False,
        "sector_claim_verified": False,
        "service_area_independently_verified": False,
        "buyer_purchase_intent_verified": False,
        "records_promoted_to_crm": 0,
        "network_access_performed_by_parser": False,
        "browser_launched": False,
        "anti_bot_bypass_used": False,
    }


def safe_offline_parse(html: bytes, *, source_url: str) -> dict[str, Any]:
    try:
        record = parse_existing_html(html, source_url=source_url)
    except (ImportError, ModuleNotFoundError):
        return {"schema_version": SCHEMA, "status": "SCRAPLING_NOT_INSTALLED",
                "network_access_performed_by_parser": False,
                "records_promoted_to_crm": 0}
    except (ValueError, TypeError):
        return {"schema_version": SCHEMA, "status": "UNTRUSTED_OR_INVALID_HTML",
                "network_access_performed_by_parser": False,
                "records_promoted_to_crm": 0}
    except Exception:
        return {"schema_version": SCHEMA, "status": "PARSER_FAILURE_HOLD",
                "network_access_performed_by_parser": False,
                "records_promoted_to_crm": 0}
    return {"status": "SCRAPLING_STRUCTURED_PAGE_PARSED", **record}
