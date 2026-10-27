"""Research-only cross-department handoff owned by the existing Media OS timer.

The handoff is an *inspection contract*, not a Predictive Cloud economic input
or an SEO/Search Fabric observation. No user, seller or business authority is
inferred from social discussions. Search and Predictive owners may read it
without a new queue, daemon, agent, DB table or scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Mapping
from collections import Counter

from empire_os.media_last30days_review_triage import (
    title_topic_match_candidate, TRIAGE_METHOD, REVIEW_FIRST, CONTEXT_ONLY,
)
from urllib.parse import urlsplit

OUTPUT = Path("runtime/media_os/last30days/research_handoff_latest.json")
SCHEMA = "empire.last30days.research_handoff.v1"
MAX_PACKS = 4
MAX_SOURCES_PER_PACK = 30
MAX_PAYLOAD_BYTES = 250_000
MAX_AGE = timedelta(days=30)
_ALLOWED = {"hackernews", "reddit", "youtube", "github", "web"}


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 48:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _source_url(raw: Any) -> str | None:
    if not isinstance(raw, str) or len(raw) > 1024:
        return None
    try:
        u = urlsplit(raw)
        hostname = u.hostname
        port = u.port
    except ValueError:
        return None
    if (u.scheme != "https" or not hostname or u.username or u.password
            or port not in (None, 443) or u.fragment
            or not re.fullmatch(r"[a-z0-9.-]+", hostname)
            or ".." in hostname or "." not in hostname
            or hostname.endswith((".internal", ".local", ".test", ".localhost"))):
        return None
    try:
        ipaddress.ip_address(hostname)
        return None
    except ValueError:
        pass
    return raw


def build_research_handoff(
    queue: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Convert validated Last30Days packs to bounded cited research proposals."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware_clock_required")
    now = now.astimezone(timezone.utc)
    if (not isinstance(queue, Mapping)
            or queue.get("schema_version") != "empire.media.research_candidates.v1"
            or queue.get("mode") != "OBSERVE"
            or queue.get("execution_authority") != "none"
            or queue.get("verified_claim_count") != 0
            or queue.get("script_ready_count") != 0
            or queue.get("public_publish_authorized") is not False
            or queue.get("automatic_script_generation_authorized") is not False
            or queue.get("actual_revenue") is not False):
        raise ValueError("unsafe_media_queue_cannot_handoff")
    entries = queue.get("candidates")
    if not isinstance(entries, list) or queue.get("candidate_count") != len(entries):
        raise ValueError("media_candidate_count_mismatch")
    packs = [c for c in entries if isinstance(c, Mapping)
             and str(c.get("research_id", "")).startswith("media-research:last30days:")]
    if len(packs) > MAX_PACKS:
        raise ValueError("too_many_last30days_packs")
    seen = set()
    topics = []
    excluded = 0
    for c in packs:
        if (c.get("schema_version") != "empire.media.research_pack.v1"
                or c.get("claims") != []
                or c.get("script_ready") is not False
                or c.get("public_publish_authorized") is not False
                or c.get("execution_authority") != "none"
                or c.get("verified_claim_count") != 0):
            raise ValueError("unsafe_last30days_pack")
        topic = c.get("topic")
        if not isinstance(topic, str) or not topic or len(topic) > 110:
            raise ValueError("invalid_research_topic")
        refs = {
            s.get("source_ref"): s for s in c.get("sources", [])
            if isinstance(s, Mapping) and isinstance(s.get("source_ref"), str)
        }
        observations = []
        for snippet in (c.get("source_snippets") or [])[:MAX_SOURCES_PER_PACK]:
            if not isinstance(snippet, Mapping):
                excluded += 1
                continue
            ref = snippet.get("source_ref")
            source = snippet.get("source")
            source_url = _source_url(snippet.get("source_url"))
            pub = _utc(snippet.get("published_at"))
            if (not isinstance(ref, str) or ref not in refs or source not in _ALLOWED
                    or not ref.startswith("last30days:source:")
                    or not source_url or pub is None
                    or pub > now or now - pub > MAX_AGE
                    or refs[ref].get("lineage_ref") != source_url):
                excluded += 1
                continue
            key = (ref, topic)
            if key in seen:
                excluded += 1
                continue
            seen.add(key)
            observations.append({
                "source_ref": ref,
                "source_type": source,
                "source_url": source_url,
                "published_at": pub.isoformat(),
                "rights": "PUBLIC_RESEARCH_REFERENCE_ONLY",
                "topic_relevance_verified": False,
                "claim_verified": False,
                "buyer_intent_verified": False,
                "local_geography_verified": False,
                "source_text_executable": False,
                # A conservative *reading order*, not independently verified
                # relevance. Keep every citation for audit even when off-topic.
                "title_topic_match_candidate": title_topic_match_candidate(
                    topic, snippet.get("title"),
                ),
            })
        topics.append({
            "research_id": c["research_id"],
            "topic": topic,
            "candidate_observation_count": len(observations),
            "observations": observations,
            "review_status": "REQUIRES_INDEPENDENT_TOPIC_RELEVANCE_AND_FACT_CHECK",
        })
    # Source reuse across topics is common with broad public searches; do not
    # mistake the same URL appearing twice for independent corroboration.
    refs_across_topics = Counter(
        x["source_ref"] for t in topics for x in t["observations"]
    )
    for topic in topics:
        first = 0
        shared = 0
        for observation in topic["observations"]:
            observation["cross_topic_reused_reference"] = (
                refs_across_topics[observation["source_ref"]] > 1
            )
            observation["review_lane"] = (
                REVIEW_FIRST if observation["title_topic_match_candidate"] else CONTEXT_ONLY
            )
            first += int(observation["title_topic_match_candidate"])
            shared += int(observation["cross_topic_reused_reference"])
        topic["review_triage"] = {
            "method": TRIAGE_METHOD,
            "title_match_candidates_unverified": first,
            "context_only_references": len(topic["observations"]) - first,
            "cross_topic_reused_references": shared,
            "human_review_required": True,
        }
    count = sum(t["candidate_observation_count"] for t in topics)
    review_first = sum(t["review_triage"]["title_match_candidates_unverified"] for t in topics)
    repeated = sum(t["review_triage"]["cross_topic_reused_references"] for t in topics)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "status": "RESEARCH_REFERENCES_AVAILABLE" if count else "NO_FRESH_ELIGIBLE_RESEARCH",
        "topic_count": len(topics),
        "source_observation_count": count,
        "excluded_observation_count": excluded,
        "review_triage": {
            "method": TRIAGE_METHOD,
            "total_citation_references": count,
            "title_match_candidates_unverified": review_first,
            "context_only_references": count - review_first,
            "cross_topic_reused_references": repeated,
            "topic_match_independently_verified": False,
            "buyer_demand_or_commercial_relevance_verified": False,
            "automatic_actions_authorized": False,
            "next_action": "HUMAN_READ_ORIGINAL_CITATIONS_AND_INDEPENDENTLY_VERIFY",
        },
        "topics": topics,
        "consumer_contracts": {
            "predictive_cloud": {
                "status": "READ_ONLY_RESEARCH_CONTEXT",
                "forecast_input_authorized": False,
                "economic_probability_or_revenue_proven": False,
                "required_next": "independent_calibration_and_outcome_evidence",
            },
            "search_intelligence": {
                "status": "OWNER_REVIEW_ONLY",
                "search_rank_or_volume_proven": False,
                "automatic_index_or_content_changes_authorized": False,
                "required_next": "independent_SERP_GSC_and_editorial_verification",
            },
            "media_os": {
                "status": "RESEARCH_PACKS_ALREADY_CONSUMED",
                "script_generation_authorized": False,
            },
            "territory_radar": {
                "status": "CONTEXT_ONLY",
                "regional_buyer_demand_verified": False,
            },
        },
        "execution_authority": "none",
        "database_write_authorized": False,
        "external_action_authorized": False,
        "public_publish_authorized": False,
        "buyer_intent_or_search_volume_from_engagement": False,
        "revenue_recognized": False,
    }


def refresh_research_handoff(
    repo_root: Path, queue: Mapping[str, Any], *, now: datetime | None = None,
) -> dict[str, Any]:
    """Atomic review export in the already allowed Media OS runtime tree."""
    out = repo_root / OUTPUT
    if not repo_root.is_absolute() or out.is_symlink() or out.parent.is_symlink():
        raise ValueError("unsafe_research_handoff_path")
    payload = build_research_handoff(queue, now=now or datetime.now(timezone.utc))
    encoded = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ValueError("research_handoff_too_large")
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=".handoff-", suffix=".tmp", dir=out.parent)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(filename, out)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)
    # Existing Media OS timer owns this opt-in cross-owner projection.
    # Write ONLY to private Media OS runtime, never the website or God’s Eye UI.
    from empire_os.godseye_last30days_context import refresh_godseye_research_context
    godseye_review = refresh_godseye_research_context(
        repo_root, payload, now=_utc(payload["generated_at"]),
    )
    return {
        "godseye_private_review": godseye_review,
        "schema_version": SCHEMA,
        "path": str(OUTPUT),
        "status": payload["status"],
        "topic_count": payload["topic_count"],
        "source_observation_count": payload["source_observation_count"],
        "execution_authority": "none",
    }
