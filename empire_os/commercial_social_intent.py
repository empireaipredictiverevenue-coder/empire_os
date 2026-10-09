"""Conservative Reddit/LinkedIn intent review for existing EmpireOS buyers.

Social content is NOT proof that a company is the author, a ready buyer, or
an approved contact. This module adds evidence-only review to the existing
company registry. No social scraping, messaging, databases or enrichment.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

from empire_os.icp_intent_relevance import classify_icp_intent

CHANNELS = frozenset({"reddit_intent", "linkedin_intent"})
SOURCE_LABELS = {"reddit_intent": "reddit", "linkedin_intent": "linkedin"}
NON_COMPANY_HOSTS = frozenset({
    "reddit.com", "linkedin.com", "facebook.com", "x.com",
    "twitter.com", "youtube.com", "google.com", "bit.ly",
    "lnkd.in", "t.co", "medium.com", "substack.com",
})
MAX_SIGNAL_AGE_SECONDS = 14 * 86400


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if date.tzinfo is None:
        return None
    return date.astimezone(timezone.utc)


def _host(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        return ""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme not in ("https", "http"):
        return ""
    hostname = (parsed.hostname or "").casefold()
    return hostname.removeprefix("www.")


def _first_party_domain(url: Any) -> str | None:
    host = _host(url)
    if (not host or host in NON_COMPANY_HOSTS
            or any(host.endswith("." + item) for item in NON_COMPANY_HOSTS)):
        return None
    return host


def _source_metrics(
    community: Mapping[str, Any] | None,
    linkedin: Mapping[str, Any] | None,
) -> dict[str, Any]:
    src = (community or {}).get("source_status") or {}
    src = src if isinstance(src, Mapping) else {}
    return {
        "community_snapshot_at": (community or {}).get("observed_at"),
        "reddit_last_collector": {
            "ok": ((src.get("reddit") or {}).get("ok") is True),
            "accepted_observations": (src.get("reddit") or {}).get("accepted_observations"),
            "source": "public_reddit_rss",
        },
        "linkedin_last_collector": {
            "ok": ((src.get("linkedin") or {}).get("ok") is True),
            "accepted_observations": (src.get("linkedin") or {}).get("accepted_observations"),
            "engine": (src.get("linkedin") or {}).get("engine"),
            "reason": ("COLLECTOR_FAILED"
                       if (src.get("linkedin") or {}).get("ok") is False
                       else "COLLECTOR_RESULT_UNVERIFIED"),
        },
        "linkedin_department": {
            "snapshot_at": (linkedin or {}).get("generated_at"),
            "candidate_count": (linkedin or {}).get("candidate_count"),
            "observed_signal_candidate_count": (
                (linkedin or {}).get("observed_signal_candidate_count")
            ),
            "resolved_decision_maker_count": (
                (linkedin or {}).get("resolved_decision_maker_count")
            ),
            "verified_contact_count": (linkedin or {}).get("verified_contact_count"),
            "human_review_ready_count": (linkedin or {}).get("human_review_ready_count"),
            "live_outbound_enabled": False,
        },
    }


def build_social_intent_review(
    signals: Mapping[str, Any],
    relationships: list[Mapping[str, Any]],
    *,
    community: Mapping[str, Any] | None = None,
    linkedin: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Join ONLY explicit external evidence links to known company domains.

    An external URL *may* be a citation, not a social author's company.
    Every match is therefore hypothesis-only and never changes the company's
    engagement, readiness or outbound status.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    known = {}
    for row in relationships:
        for name in row.get("identity_domains") or []:
            known[str(name).casefold()] = row["entity_key"]
    counts = Counter()
    observed = []
    seen_urls = set()
    linked = []
    classified_counts = Counter()
    product_hypotheses = Counter()
    for key, raw in signals.items():
        if not isinstance(raw, Mapping) or raw.get("source") not in CHANNELS:
            continue
        channel = str(raw["source"])
        counts[channel] += 1
        if raw.get("status") not in ("unresolved", "needs_review"):
            continue
        embedded = raw.get("raw")
        embedded = embedded if isinstance(embedded, Mapping) else {}
        detail = embedded.get("community_intent")
        detail = detail if isinstance(detail, Mapping) else {}
        stamp = _timestamp(detail.get("observed_at"))
        if not stamp or not 0 <= (now-stamp).total_seconds() <= MAX_SIGNAL_AGE_SECONDS:
            counts["stale_or_unproven_observation"] += 1
            continue
        if len(str(key)) > 100:
            continue
        try:
            score = min(100, max(0, int(detail.get("intent_score", raw.get("lead_score")) or 0)))
        except (ValueError, TypeError):
            score = 0
        public_url = detail.get("url") or raw.get("url")
        if not isinstance(public_url, str) or not _host(public_url):
            continue
        if public_url in seen_urls:
            continue
        seen_urls.add(public_url)
        urls = embedded.get("evidence_urls") or detail.get("evidence_urls") or []
        if not isinstance(urls, (list, tuple)):
            urls = []
        potential = {}
        for ref in urls[:15]:
            domain = _first_party_domain(ref)
            if domain in known:
                potential[known[domain]] = {
                    "entity_key": known[domain], "evidence_website": str(ref)[:2048],
                }
        classification = classify_icp_intent(detail)
        classified_counts[classification["intent_class"]] += 1
        if (score < 35 and not potential
                and classification["intent_class"] not in (
                    "EXPLICIT_REQUEST_UNVERIFIED",
                    "OPERATOR_PROBLEM_SELF_REPORTED",
                )):
            continue
        for offer in classification["candidate_offer_hypotheses"]:
            if classification["intent_class"] in (
                "EXPLICIT_REQUEST_UNVERIFIED",
                "OPERATOR_PROBLEM_SELF_REPORTED",
            ):
                product_hypotheses[offer["offer_key"]] += 1
        item = {
            "signal_id": str(key)[:100],
            "channel": SOURCE_LABELS[channel],
            "public_post_url": public_url[:2048],
            "observed_at": stamp.isoformat(),
            "reported_intent_score": score,
            "icp_relevance": classification,
            "niche": str(detail.get("niche") or raw.get("niche") or "")[:65],
            "potential_company_matches": list(potential.values()),
            "poster_company_identity_verified": False,
            "buyer_purchase_intent_verified": False,
            "contact_verified": False,
            "outbound_authorized": False,
            "next_action": ("REVIEW_EXPLICIT_EXTERNAL_COMPANY_LINK"
                            if potential else "IDENTIFY_COMPANY_AND_VERIFY_POSTER"),
        }
        observed.append(item)
        if potential:
            linked.append(item)
    observed.sort(key=lambda x: (-x["reported_intent_score"], x["channel"], x["signal_id"]))
    # Avoid drowning Reddit in dozens of broader LinkedIn snippets.
    reddit = [x for x in observed if x["channel"] == "reddit"][:8]
    linked_in = [x for x in observed if x["channel"] == "linkedin"][:8]
    review = sorted(reddit + linked_in,
                    key=lambda x: (-x["reported_intent_score"], x["channel"]))
    metrics = _source_metrics(community, linkedin)
    return {
        "schema_version": "empire.commercial_social_intent_review.v1",
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "sources": {"reddit_intent": counts["reddit_intent"],
                    "linkedin_intent": counts["linkedin_intent"]},
        "evidence_bearing_recent_signal_count": len(observed),
        "signals_with_potential_company_link_count": len(linked),
        "verified_poster_to_company_identity_count": 0,
        "verified_commercial_buying_intent_count": 0,
        "stale_or_unproven_observation_count": counts["stale_or_unproven_observation"],
        "intent_class_counts": dict(sorted(classified_counts.items())),
        "candidate_offer_interest_signals": [
            {
                "offer_key": key,
                "signal_observations": qty,
                "paid_demand_verified": False,
            }
            for key, qty in product_hypotheses.most_common()
        ],
        "identity_unverified_review_queue": review,
        "review_queue_truncated": len(review) < len(observed),
        "linkedin_and_reddit_runtime": metrics,
        "historical_post_publication_date_independently_verified": False,
        "contact_verified": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }
