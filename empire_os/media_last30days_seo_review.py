"""Automatically refreshed, owner-readable SEO research review — no SEO mutations.

Part of the existing Media OS Last30Days producer/timer. Evidence stays
social research until the ORIGINAL Search Intelligence owner independently
verifies sources, GSC, SERP, and publishing authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping
from urllib.parse import urlsplit

OUTPUT = Path("runtime/media_os/last30days/seo_owner_review_latest.json")
SCHEMA = "empire.last30days.seo_owner_review.v1"
MAX_BYTES = 120_000
MAX_TOPICS = 4
MAX_OBSERVATIONS = 120
MAX_AGE = timedelta(hours=2)
REVIEW_FIRST = "READ_TITLE_MATCH_FIRST_REQUIRES_HUMAN_CHECK"


def _valid_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 1024:
        return False
    try:
        u = urlsplit(value)
        host = u.hostname
        port = u.port
    except ValueError:
        return False
    if (u.scheme != "https" or not host or u.username or u.password
            or port not in (None, 443) or u.fragment or ".." in host
            or not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host
            or host.endswith((".local", ".internal", ".test", ".localhost"))):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def build_seo_owner_review(handoff: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware_clock_required")
    now = now.astimezone(timezone.utc)
    if not isinstance(handoff, Mapping):
        raise ValueError("invalid_research_handoff")
    try:
        generated = datetime.fromisoformat(str(handoff["generated_at"]).replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError):
        raise ValueError("invalid_research_generation") from None
    if (generated.tzinfo is None or generated > now + timedelta(minutes=1)
            or now - generated > MAX_AGE):
        raise ValueError("stale_research_handoff")
    contract = handoff.get("consumer_contracts", {}).get("search_intelligence", {})
    if (handoff.get("schema_version") != "empire.last30days.research_handoff.v1"
            or handoff.get("mode") != "OBSERVE"
            or handoff.get("execution_authority") != "none"
            or handoff.get("external_action_authorized") is not False
            or handoff.get("database_write_authorized") is not False
            or handoff.get("public_publish_authorized") is not False
            or handoff.get("revenue_recognized") is not False
            or handoff.get("buyer_intent_or_search_volume_from_engagement") is not False
            or contract.get("status") != "OWNER_REVIEW_ONLY"
            or contract.get("search_rank_or_volume_proven") is not False
            or contract.get("automatic_index_or_content_changes_authorized") is not False):
        raise ValueError("handoff_not_authorized_for_seo_review")
    topics = handoff.get("topics")
    if (not isinstance(topics, list) or not 0 <= len(topics) <= MAX_TOPICS
            or handoff.get("topic_count") != len(topics)):
        raise ValueError("invalid_topic_count")
    review_topics = []
    total = 0
    review_first_count = 0
    unique = set()
    for topic in topics:
        if not isinstance(topic, Mapping):
            raise ValueError("invalid_research_topic")
        title = topic.get("topic")
        rows = topic.get("observations")
        if (not isinstance(title, str) or not 1 <= len(title) <= 110
                or not isinstance(rows, list) or len(rows) > 30
                or len(rows) != topic.get("candidate_observation_count")):
            raise ValueError("invalid_topic_references")
        total += len(rows)
        if total > MAX_OBSERVATIONS:
            raise ValueError("too_many_citation_references")
        selected = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("invalid_reference")
            ref = row.get("source_ref")
            if (not isinstance(ref, str) or len(ref) > 128
                    or not ref.startswith("last30days:source:")
                    or not _valid_url(row.get("source_url"))
                    or row.get("rights") != "PUBLIC_RESEARCH_REFERENCE_ONLY"
                    or row.get("topic_relevance_verified") is not False
                    or row.get("claim_verified") is not False
                    or row.get("buyer_intent_verified") is not False
                    or row.get("source_text_executable") is not False):
                raise ValueError("untrusted_reference")
            if row.get("review_lane") != REVIEW_FIRST:
                continue
            if row.get("title_topic_match_candidate") is not True:
                raise ValueError("invalid_relevance_triage")
            if ref in unique:
                continue
            unique.add(ref)
            selected.append({
                "source_ref": ref,
                "source_url": row["source_url"],
                "source_type": row.get("source_type"),
                "published_at": row.get("published_at"),
                "cross_topic_reused_reference": row.get("cross_topic_reused_reference") is True,
                "candidate_type": "UNVERIFIED_TITLE_MATCH_FOR_EDITORIAL_REVIEW",
                "suggested_owner_validation": "READ_SOURCE_THEN_VALIDATE_GSC_SERP_AND_SEARCH_INTENT",
            })
            review_first_count += 1
        review_topics.append({
            "topic": title,
            "original_reference_count": len(rows),
            "review_first_unverified_count": len(selected),
            "references_for_manual_review": selected,
            "relevance_verified": False,
            "search_demand_verified": False,
            "search_volume_or_rankings": None,
        })
    if total != handoff.get("source_observation_count"):
        raise ValueError("source_reference_count_mismatch")
    return {
        "schema_version": SCHEMA,
        "status": "REVIEW_CITATIONS_READY" if review_first_count else "NO_TITLE_MATCHED_CITATIONS",
        "mode": "OWNER_REVIEW_ONLY",
        "generated_at": now.isoformat(),
        "source_handoff_generated_at": generated.astimezone(timezone.utc).isoformat(),
        "original_source_observation_count": total,
        "review_first_unique_citation_count": review_first_count,
        "topics": review_topics,
        "owner": "ORIGINAL_SEARCH_INTELLIGENCE_IMPLEMENTATION_OWNER",
        "source_data_kind": "PUBLIC_COMMUNITY_DISCUSSION_NOT_GOOGLE_SEARCH_DATA",
        "owner_next_action": "REVIEW_REFERENCES_THEN_VALIDATE_AGAINST_GSC_AND_SERP",
        "independent_source_relevance_verified": False,
        "gsc_queries_or_impressions_observed": False,
        "search_volume_verified": False,
        "rankings_or_clicks_verified": False,
        "commercial_demand_or_revenue_verified": False,
        "publication_authorized": False,
        "seo_recommendation_accepted_by_owner": False,
        "automated_seo_changes_authorized": False,
        "execution_authority": "none",
        "external_action_authorized": False,
        "database_write_authorized": False,
        "public_publish_authorized": False,
        "read_only_owner_artifact": True,
    }


def refresh_seo_owner_review(repo_root: Path, handoff: Mapping[str, Any],
                             *, now: datetime) -> dict[str, Any]:
    if not repo_root.is_absolute() or repo_root.is_symlink():
        raise ValueError("canonical_absolute_root_required")
    target = repo_root / OUTPUT
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("unsafe_seo_owner_review_path")
    result = build_seo_owner_review(handoff, now=now)
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if len(payload) > MAX_BYTES:
        raise ValueError("seo_review_payload_too_large")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix=".seo-review-", suffix=".tmp", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        os.replace(staged, target)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return {
        "status": result["status"],
        "owner": result["owner"],
        "path": str(OUTPUT),
        "review_first_unique_citations": result["review_first_unique_citation_count"],
        "original_reference_count": result["original_source_observation_count"],
        "seo_code_modified": False,
        "no_automatic_publishing_or_indexing": True,
    }
