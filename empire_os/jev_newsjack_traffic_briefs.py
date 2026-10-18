"""NewsJack/JEV → verified existing Empire landing pages → editorial research briefs.

Uses the *existing* first-party public HTML inspector. The only pages it may
inspect are the literal pre-approved Empire URLs below, never URLs from a
news headline or user-controlled signal. No publishing, page edits, outbound
messages, traffic claims, or commercial outcomes.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic
from empire_os.research.public_page_inspector import inspect_public_html


# This is routing to existing owned pages, not permission to modify them.
APPROVED_PAGE_ROUTES = {
    ("solar", "GB"): "https://empire-ai.co.uk/industries/solar",
    ("roofing", "US"): "https://empire-ai.co.uk/industries/roofing",
    ("ai", "GB"): "https://empire-ai.co.uk/commercial",
    ("ai", "US"): "https://empire-ai.co.uk/commercial",
}
COMMERCIAL_CONTACT = "https://empire-ai.co.uk/commercial"
REQUIRED_PAGE_TERMS = {
    "solar": ("solar", "installer"),
    "roofing": ("roofing", "buyer"),
    "ai": ("consultancy", "revenue"),
}
EDITORIAL_QUESTIONS = {
    "solar": (
        "What does the verified development mean for a UK solar installer or buyer?",
        "Which local evidence, dates and eligibility conditions would change a decision?",
    ),
    "roofing": (
        "Which US roofing buyers, properties or territories could this affect?",
        "What dated evidence should contractors verify before responding?",
    ),
    "ai": (
        "Which business decision does the development help clarify?",
        "What measurable evidence would justify an assessment or consultancy conversation?",
    ),
}


def prepare_editorial_traffic_reviews(
    signals: Sequence[Mapping[str, Any]], *,
    as_of: str,
    inspector: Callable[[str], Mapping[str, Any]] = inspect_public_html,
    provider: Any = None,
) -> dict[str, Any]:
    """Construct reviewed research previews against verified, existing pages.

    Signal source truth remains with the official/research source owners.
    Inspected page HTML only verifies the destination, not a working enquiry
    submission or truth of a news claim.
    """
    if not isinstance(signals, (list, tuple)) or len(signals) > 50:
        raise ValueError("bounded signal batch of at most 50 required")
    if not all(isinstance(s, Mapping) for s in signals):
        raise ValueError("signal mappings required")
    if not callable(inspector):
        raise ValueError("existing public inspector required")

    # Collect known routes only. User data cannot supply a destination host,
    # URL, port, or arbitrary path to the inspector.
    selected = {}
    for item in signals:
        sector, market = item.get("sector"), item.get("market")
        if not isinstance(sector, str) or not isinstance(market, str):
            continue
        key = (sector.lower().strip(), market.upper().strip())
        if key in APPROVED_PAGE_ROUTES:
            selected[key] = APPROVED_PAGE_ROUTES[key]
    paths = set(selected.values())
    if paths:
        paths.add(COMMERCIAL_CONTACT)

    observed: dict[str, dict[str, Any]] = {}
    for page in sorted(paths):
        try:
            record = inspector(page)
        except (RuntimeError, ValueError, OSError, TypeError):
            record = {"status": "INSPECTOR_UNAVAILABLE"}
        if not isinstance(record, Mapping):
            record = {"status": "INSPECTOR_INVALID"}
        title = record.get("page_title")
        headings = record.get("document_headings")
        digest = record.get("content_sha256")
        ready = (
            record.get("status") == "ORIGINAL_HTML_HEADINGS_INSPECTED"
            and record.get("source_url") == page
            and record.get("http_status") == 200
            and isinstance(digest, str) and len(digest) == 64
            and all(x in "0123456789abcdef" for x in digest)
            and isinstance(title, str) and bool(title.strip())
            and isinstance(headings, list) and bool(headings)
            and all(isinstance(h, str) for h in headings)
        )
        observed[page] = {
            "live_verified": ready,
            "title": title[:180] if ready else None,
            "headings": headings[:4] if ready else [],
            "content_sha256": digest if ready else None,
            "status": "VERIFIED_EXISTING_HTML" if ready else "NOT_VERIFIED",
            "evidence_ref": f"empire:owned-html:{digest}" if ready else None,
        }

    candidates = []
    for item in signals:
        row = dict(item)
        sector = str(item.get("sector") or "").lower().strip()
        market = str(item.get("market") or "").upper().strip()
        page = selected.get((sector, market))
        proof = observed.get(page, {})
        text = ((proof.get("title") or "") + " " +
                " ".join(proof.get("headings") or [])).lower()
        terms = REQUIRED_PAGE_TERMS.get(sector, ())
        matched = bool(page and proof.get("live_verified") and
                       all(term in text for term in terms))
        if matched:
            row["destination_url"] = page
            row["destination_live_verified"] = True
            row["destination_evidence_refs"] = [proof["evidence_ref"]]
        else:
            # Never copy caller-supplied claims of a live page into a
            # trusted inspector result.
            row.pop("destination_evidence_refs", None)
            row["destination_live_verified"] = False
            row.pop("destination_url", None)
        candidates.append(row)

    scoped = review_newsjack_jev_traffic(
        candidates,
        as_of=as_of,
        approved_sectors=["solar", "roofing", "ai"],
        approved_markets=["GB", "US"],
        approved_destination_urls=tuple(paths),
        provider=provider,
    )
    editor_queue = []
    for candidate in scoped["candidates"]:
        sector = candidate.get("sector")
        market = candidate.get("market")
        matched_page = selected.get((sector, market))
        inspected = observed.get(matched_page, {})
        accepted = (candidate.get("status") in
                    ("RESEARCH_REVIEW", "CONTENT_BRIEF_REVIEW") and
                    candidate.get("destination_operator_attested") is True)
        commercial_ready = observed.get(COMMERCIAL_CONTACT, {}).get("live_verified") is True
        notes = list(candidate.get("missing_evidence") or [])
        if not accepted:
            notes.append("verified_relevant_live_destination_or_fresh_source_missing")
        if not commercial_ready:
            notes.append("commercial_destination_not_verified")
        editor_queue.append({
            "signal_id": candidate.get("signal_id"),
            "source_url": candidate.get("primary_source_url"),
            "source_title_unverified": candidate.get("title"),
            "market": market, "sector": sector,
            "status": "EDITORIAL_RESEARCH_PREVIEW" if accepted
                      else "HOLD_FOR_RESEARCH",
            "page_url": matched_page if accepted else None,
            "page_content_sha256": inspected.get("content_sha256") if accepted else None,
            "page_title_observed": inspected.get("title") if accepted else None,
            "buyer_questions_to_investigate": list(EDITORIAL_QUESTIONS.get(sector, ()))
            if accepted else [],
            "cta_existing_commercial_page": COMMERCIAL_CONTACT if accepted and commercial_ready else None,
            "source_evidence_refs": list(candidate.get("evidence_refs") or []),
            "research_gaps": sorted(set(notes)),
            "search_query_observation": candidate.get("search_observation"),
            "jev_classification": candidate.get("jev_shadow_decision"),
            "claims_independently_fact_checked": False,
            "story_publication_authorized": False,
            "page_mutation_authorized": False,
            "published_article_count": 0,
            "attributable_visitors": None,
            "qualified_enquiries": None,
            "realized_revenue": None,
            "execution_authority": "none",
        })
    return {
        "schema_version": "empire.organic.jev_editorial_traffic_review.v1",
        "mode": "OBSERVE",
        "news_candidates": scoped["candidate_count"],
        "editorial_research_preview_count": sum(
            x["status"] == "EDITORIAL_RESEARCH_PREVIEW" for x in editor_queue
        ),
        "verified_existing_page_count": sum(
            v["live_verified"] for v in observed.values()),
        "observed_owned_pages": observed,
        "review_queue": editor_queue,
        "no_new_page_created": True,
        "newsjack_installed_or_invoked": False,
        "live_publication": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
