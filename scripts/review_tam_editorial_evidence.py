#!/usr/bin/env python3
"""Fail-closed one-shot reviewer for the first-party TAM buying-intent draft.

Binds source references to existing EmpireOS proof and sends the topic through
the canonical keyword strategy reviewer. This is NOT an editorial signoff or
a URL/publication/traffic authority. No DB/network/mail/site/timer writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from empire_os.keyword_universe import review_keyword_record

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "docs/seo/BUYER_INTENT_TAM_EDITORIAL_DRAFT_20261015.md"
SCHEMA = "empire.seo.tam_editorial_provenance_review.v1"
SOURCE_REFS = {
    "SEARCH-GSC-01": [
        "docs/commercial/LIVE_GSC_LEGACY_404_REVENUE_TRIAGE_20261015.md",
        "scripts/review_live_search_404_revenue_readonly.py",
    ],
    "EMPIRE-CONTROLS-01": [
        "empire_os/buyer_recovery_action_desk.py",
        "empire_os/first_party_sales_interest.py",
        "docs/commercial/FOUNDER_SALES_ACQUISITION_CRM_RECONCILIATION_20261015.md",
    ],
    "EMPIRE-OFFERS-01": [
        "empire_os/self_serve_checkout_api.py",
        "empire_os/predictive_revenue_self_serve.py",
    ],
    "GOOGLE-PEOPLE-FIRST-01": [
        # Unlike local evidence, official guidance is attributed by URL only.
        "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
    ],
}
MIN_ARTICLE_WORDS = 700
MAX_ARTICLE_WORDS = 2200
MAX_DOCUMENT_BYTES = 28_000
KEYWORD_INPUT = {
    "keyword": "which companies in my tam are ready to buy",
    "cluster_key": "buyer_readiness_verified_intent",
    "intent_class": "problem",
    "product_key": "predictive_revenue_intelligence",
    "icp_key": "b2b_revenue_operations_and_founders",
    "funnel_stage": "consideration",
    "asset_type": "guide",
    "cta_key": "nonbinding_commercial_enquiry",
    # Observed intent to research ONE query is not measured keyword volume.
    "evidence_refs": ["SEARCH-GSC-01", "EMPIRE-CONTROLS-01",
                      "EMPIRE-OFFERS-01", "GOOGLE-PEOPLE-FIRST-01"],
}


def _held(code: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "status": "HELD_EDITORIAL_SOURCE_REVIEW",
        "reason_code": code,
        "read_only": True,
        "raw_contacts_read": False,
        "database_writes": False,
        "network_calls": False,
        "outbound_sent": False,
        "publishing_authorized": False,
        "indexation_authorized": False,
        "redirect_authorized": False,
        "founder_release_approved": False,
        "execution_authority": "none",
    }


def inspect_draft(text: str, *, exists: Any, byte_size: int | None = None) -> dict[str, Any]:
    if not isinstance(text, str):
        return _held("DRAFT_NOT_TEXT")
    if byte_size is None:
        byte_size = len(text.encode("utf-8"))
    if byte_size > MAX_DOCUMENT_BYTES or byte_size < 3000:
        return _held("DRAFT_UNBOUNDED_OR_TRIVIAL")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return _held("DRAFT_METADATA_MISSING")
    _, front, rest = text.split("---\n", 2)
    split_key = "\n## Editorial release notes — not public article copy"
    if split_key not in rest:
        return _held("SOURCE_EDITORIAL_NOTES_NOT_ISOLATED")
    public, editorial_notes = rest.split(split_key, 1)
    required_metadata = (
        "status: DRAFT_REQUIRES_EDITORIAL_AND_FOUNDER_RELEASE",
        "canonical_url: NOT_DECIDED",
        "publication_authorized: false",
        "indexation_authorized: false",
        "redirect_authorized: false",
        "outbound_authorized: false",
    )
    if any(line not in front.splitlines() for line in required_metadata):
        return _held("AUTHORISATION_OR_CANONICAL_GATE_MISSING")

    words = re.findall(r"\b[\w’-]+\b", public, flags=re.UNICODE)
    if not MIN_ARTICLE_WORDS <= len(words) <= MAX_ARTICLE_WORDS:
        return _held("ARTICLE_LENGTH_REQUIRES_HUMAN_REVIEW")
    sections = (
        "# How to tell which companies in your total addressable market are actually ready to buy",
        "## The five levels of buyer readiness",
        "## Signals worth investigating—and their traps",
        "## A research checklist you can use today",
        "## What a buyer-readiness workflow should report",
        "## Where Predictive Revenue fits",
        "## Frequently asked questions",
        "## Request a scoped commercial discussion",
    )
    if any(section not in public for section in sections):
        return _held("READER_QUESTION_ORIGINAL_STRUCTURE_INCOMPLETE")
    levels = (
        "**1. Market fit**", "**2. Observable change**",
        "**3. Corroborated need**", "**4. Declared buying interest**",
        "**5. Commercial commitment**",
    )
    if any(level not in public for level in levels):
        return _held("BUYER_INTENT_EVIDENCE_LADDER_INCOMPLETE")

    # Only two approved nonbinding CTA links in the reader-facing asset.
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", public)
    if sorted(links) != ["/commercial", "/predictive-revenue"]:
        return _held("UNVERIFIED_EXTERNAL_OR_BINDING_CTA")
    forbidden = (
        "guaranteed ROI", "guaranteed revenue", "guaranteed buyers",
        "proven conversion uplift", "97% accurate", "99% accurate",
        "live checkout", "buy now", "send us leads", "verified customers",
    )
    if any(value.casefold() in public.casefold() for value in forbidden):
        return _held("UNSUPPORTED_SALES_CLAIM")
    if re.search(r"(?:^|\s)(?:\d{2,3})%\s+(?:accuracy|conversion|uplift)", public, re.I):
        return _held("UNSUPPORTED_MEASURED_PERFORMANCE_CLAIM")
    if "not probabilities" not in public.lower():
        return _held("SIGNALS_UNLAWFULLY_PRESENTED_AS_PROBABILITIES")
    if not all(term in public.lower() for term in ("suppression", "source", "consent", "identity")):
        return _held("GOVERNANCE_CHECKS_MISSING")

    refs = {}
    for ref, sources in SOURCE_REFS.items():
        if ref not in editorial_notes:
            return _held("MISSING_EDITORIAL_PROVENANCE_REF")
        local = []
        for name in sources:
            if name.startswith("https://"):
                if name not in editorial_notes:
                    return _held("EXTERNAL_OFFICIAL_SOURCE_URL_MISSING")
                continue
            if not exists(ROOT / name):
                return _held("SOURCE_EVIDENCE_FILE_UNAVAILABLE")
            local.append(name)
        refs[ref] = local or ["GOOGLE_SEARCH_CENTRAL_GUIDANCE_LINK"]

    check = review_keyword_record(KEYWORD_INPUT)
    if check["review_ready"] is not True or check["opportunity"]["available"] is not False:
        # Without numeric, independently justified inputs, do NOT invent a
        # demand or conversion estimate or imply that SEO will bring buyers.
        return _held("UNSUPPORTED_KEYWORD_FORECAST_OR_STRATEGY")
    return {
        "schema_version": SCHEMA,
        "status": "EVIDENCED_DRAFT_READY_FOR_HUMAN_REVIEW",
        "read_only": True,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "draft_asset_id": "empire-seo-tam-buyer-readiness-20261015",
        "public_article_word_count": len(words),
        "source_evidence_refs_verified": list(refs),
        "local_source_reference_file_count": sum(
            len(x) for x in refs.values() if x != ["GOOGLE_SEARCH_CENTRAL_GUIDANCE_LINK"]
        ),
        "keyword_review_ready": True,
        "keyword_opportunity_score": None,
        "observed_keyword_search_volume": None,
        "known_revenue_topic_disclosed_impressions": 1,
        "reader_cta_paths": links,
        "suggested_destination": "ASTRA_REVIEW_EXISTING_SITE_NOT_RESTORED_LEGACY_URL",
        "editorial_review_approved": False,
        "external_fact_check_approved": False,
        "privacy_and_legal_review_approved": False,
        "founder_release_approved": False,
        "publishing_authorized": False,
        "indexation_authorized": False,
        "redirect_authorized": False,
        "outbound_sent": False,
        "network_calls": False,
        "database_writes": False,
        "raw_contacts_read": False,
        "execution_authority": "none",
    }


def run(path: Path = DRAFT) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            return _held("DRAFT_FILE_UNTRUSTED")
        stat = path.stat()
        if stat.st_size > MAX_DOCUMENT_BYTES:
            return _held("DRAFT_UNBOUNDED_OR_TRIVIAL")
        doc = path.read_text("utf-8")
        return inspect_draft(doc, exists=lambda p: p.is_file() and not p.is_symlink(),
                             byte_size=stat.st_size)
    except (OSError, UnicodeError):
        return _held("DRAFT_FILE_READ_UNAVAILABLE")
    except Exception:
        return _held("UNEXPECTED_EDITORIAL_REVIEW_FAILURE")


def main() -> int:
    report = run()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "EVIDENCED_DRAFT_READY_FOR_HUMAN_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
