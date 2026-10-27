"""Private God's Eye research context from the ORIGINAL Last30Days Media OS handoff.

The existing Media OS timer owns the source. This bounded projection merely
lets an authorised God’s Eye UI show dated, unverified topic research. It
NEVER assigns lat/lon, predicts purchases, extracts personal profiles, grants
publish rights, or creates a second scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping

from empire_os.media_last30days_handoff import SCHEMA as SOURCE_SCHEMA, _source_url, _utc

SCHEMA = "empire.godseye.last30days_context.v1"
OUTPUT = Path("runtime/media_os/last30days/godseye_research_latest.json")
MAX_TOPICS = 4
MAX_REFERENCES_PER_TOPIC = 8
MAX_AGE = timedelta(hours=2)
MAX_BODY = 32_000


def build_godseye_research_context(
    handoff: Mapping[str, Any], *, now: datetime,
) -> dict[str, Any]:
    """A small reviewed *non-geospatial* subset, no executable third-party text."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_aware_clock_required")
    now = now.astimezone(timezone.utc)
    generated = _utc(handoff.get("generated_at"))
    if (not isinstance(handoff, Mapping)
            or handoff.get("schema_version") != SOURCE_SCHEMA
            or handoff.get("mode") != "OBSERVE"
            or handoff.get("execution_authority") != "none"
            or handoff.get("external_action_authorized") is not False
            or handoff.get("public_publish_authorized") is not False
            or handoff.get("revenue_recognized") is not False
            or handoff.get("buyer_intent_or_search_volume_from_engagement") is not False
            or generated is None or generated > now or now-generated > MAX_AGE):
        raise ValueError("untrusted_or_stale_last30days_handoff")
    topics = handoff.get("topics")
    if not isinstance(topics, list) or len(topics) > MAX_TOPICS or handoff.get("topic_count") != len(topics):
        raise ValueError("last30days_topic_count_invalid")
    existing_counts = sum(x.get("candidate_observation_count", 0) for x in topics if isinstance(x, Mapping))
    if handoff.get("source_observation_count") != existing_counts:
        raise ValueError("last30days_source_count_invalid")
    output_topics = []
    used = set()
    excluded = 0
    for row in topics:
        if (not isinstance(row, Mapping)
                or row.get("review_status") != "REQUIRES_INDEPENDENT_TOPIC_RELEVANCE_AND_FACT_CHECK"
                or not isinstance(row.get("topic"), str)
                or not 1 <= len(row["topic"]) <= 110
                or not isinstance(row.get("observations"), list)
                or len(row["observations"]) > 30
                or row.get("candidate_observation_count") != len(row["observations"])):
            raise ValueError("malformed_last30days_topic")
        if row["topic"] in used:
            raise ValueError("duplicate_last30days_topic")
        used.add(row["topic"])
        sources = []
        for source in row["observations"][:MAX_REFERENCES_PER_TOPIC]:
            if not isinstance(source, Mapping):
                excluded += 1
                continue
            published = _utc(source.get("published_at"))
            url = _source_url(source.get("source_url"))
            if (not url or published is None or published > now
                    or now - published > timedelta(days=30)
                    or source.get("source_type") not in ("reddit", "hackernews")
                    or source.get("rights") != "PUBLIC_RESEARCH_REFERENCE_ONLY"
                    or source.get("topic_relevance_verified") is not False
                    or source.get("claim_verified") is not False
                    or source.get("buyer_intent_verified") is not False
                    or source.get("local_geography_verified") is not False
                    or source.get("source_text_executable") is not False):
                excluded += 1
                continue
            sources.append({
                "url": url,
                "provider": source["source_type"],
                "published_at": published.isoformat(),
                "topic_relevance_verified": False,
            })
        output_topics.append({
            "topic": row["topic"],
            "observations_seen": row["candidate_observation_count"],
            "citations_for_review": sources,
            "review_state": "UNVERIFIED_RESEARCH_REFERENCES",
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source_handoff_at": generated.isoformat(),
        "status": "RESEARCH_REVIEW_AVAILABLE" if any(t["citations_for_review"] for t in output_topics) else "NO_VALID_RESEARCH_REFERENCES",
        "topic_count": len(output_topics),
        "source_observation_count": existing_counts,
        "excluded_reference_count": excluded,
        "topics": output_topics,
        "display_scope": "RESEARCH_PANEL_ONLY_NOT_MAP_MARKERS",
        "topic_relevance_verified": False,
        "forecast_or_commercial_buyer_verified": False,
        "search_volume_or_market_size_verified": False,
        "geographic_coordinates_verified": False,
        "revenue_verified": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def refresh_godseye_research_context(repo_root: Path, handoff: Mapping[str, Any], *, now: datetime | None = None) -> dict:
    if not repo_root.is_absolute() or repo_root.is_symlink():
        raise ValueError("absolute_canonical_root_required")
    payload = build_godseye_research_context(handoff, now=now or datetime.now(timezone.utc))
    encoded = (json.dumps(payload, indent=2, sort_keys=True)+"\n").encode("utf-8")
    if len(encoded) > MAX_BODY:
        raise ValueError("godseye_research_context_too_large")
    target = repo_root / OUTPUT
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("unsafe_godseye_research_output_path")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".godseye-research-", suffix=".tmp", dir=target.parent)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return {
        "path": str(OUTPUT),
        "schema_version": SCHEMA,
        "status": payload["status"],
        "topics": payload["topic_count"],
        "citations_for_review": sum(len(t["citations_for_review"]) for t in payload["topics"]),
        "map_markers_created": 0,
        "publish_authorized": False,
    }
