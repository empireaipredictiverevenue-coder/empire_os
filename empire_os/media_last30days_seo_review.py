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
PROJECTION_REVISION = 2  # age-window labels added; forces one safe rebuild
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



def _previous_snapshot(previous: Mapping[str, Any] | None, *, now: datetime, source_time: datetime) -> set[tuple[str, str]] | None:
    """One-cycle delta only: previously seen DOES NOT mean owner reviewed."""
    if previous is None:
        return None
    if (not isinstance(previous, Mapping) or previous.get("schema_version") != SCHEMA
            or previous.get("mode") != "OWNER_REVIEW_ONLY"
            or previous.get("owner") != "ORIGINAL_SEARCH_INTELLIGENCE_IMPLEMENTATION_OWNER"
            or previous.get("publication_authorized") is not False
            or previous.get("automated_seo_changes_authorized") is not False
            or previous.get("seo_recommendation_accepted_by_owner") is not False):
        raise ValueError("untrusted_prior_review_snapshot")
    try:
        previous_time = datetime.fromisoformat(
            str(previous["source_handoff_generated_at"]).replace("Z", "+00:00")
        )
    except (TypeError, ValueError, KeyError):
        raise ValueError("untrusted_prior_review_timestamp") from None
    if (previous_time.tzinfo is None or previous_time > source_time
            or previous_time > now + timedelta(minutes=1)):
        raise ValueError("prior_review_snapshot_newer_than_current_source")
    # A missing/very old previous snapshot cannot establish whether material is NEW.
    if source_time - previous_time > timedelta(days=2):
        return None
    topics = previous.get("topics")
    if not isinstance(topics, list) or len(topics) > MAX_TOPICS:
        raise ValueError("untrusted_prior_review_topics")
    seen: set[tuple[str, str]] = set()
    for topic in topics:
        if not isinstance(topic, Mapping):
            raise ValueError("untrusted_prior_review_topic")
        rows = topic.get("references_for_manual_review")
        if not isinstance(rows, list) or len(rows) > 30:
            raise ValueError("untrusted_prior_review_references")
        for row in rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("source_ref"), str) or not _valid_url(row.get("source_url")):
                raise ValueError("untrusted_prior_review_reference")
            seen.add((row["source_ref"], row["source_url"]))
    return seen



def _source_publication_age(value: Any, *, now: datetime) -> tuple[int | None, str, bool]:
    """Date-age estimate, NOT verification of the externally supplied date."""
    if not isinstance(value, str) or len(value) < 10 or len(value) > 48:
        return None, "UNVERIFIED_SOURCE_DATE", False
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            issued = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        else:
            issued = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if issued.tzinfo is None or issued.utcoffset() is None:
            return None, "UNVERIFIED_SOURCE_DATE", False
        age = (now.date() - issued.astimezone(timezone.utc).date()).days
    except (ValueError, TypeError, OverflowError):
        return None, "UNVERIFIED_SOURCE_DATE", False
    if age < 0:
        return age, "FUTURE_SOURCE_DATE_HOLD", False
    if age > 30:
        return age, "OUTSIDE_LAST30DAYS_SCOPE_HOLD", False
    if age <= 7:
        return age, "RECENT_0_TO_7_DAYS", True
    if age <= 21:
        return age, "ACTIVE_8_TO_21_DAYS", True
    return age, "EXPIRING_22_TO_30_DAYS", True


def build_seo_owner_review(handoff: Mapping[str, Any], *, now: datetime,
                           previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    prior_refs = _previous_snapshot(previous, now=now, source_time=generated)
    review_topics = []
    total = 0
    review_first_count = 0
    new_count = 0
    fresh_review_count = 0
    source_age_counts = {
        "RECENT_0_TO_7_DAYS": 0,
        "ACTIVE_8_TO_21_DAYS": 0,
        "EXPIRING_22_TO_30_DAYS": 0,
        "OUTSIDE_LAST30DAYS_SCOPE_HOLD": 0,
        "UNVERIFIED_SOURCE_DATE": 0,
        "FUTURE_SOURCE_DATE_HOLD": 0,
    }
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
        topic_new = 0
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
            new_to_previous = ((ref, row["source_url"]) not in prior_refs) if prior_refs is not None else None
            if new_to_previous:
                new_count += 1
                topic_new += 1
            source_age, age_band, in_last_30 = _source_publication_age(
                row.get("published_at"), now=now,
            )
            source_age_counts[age_band] += 1
            fresh_review_count += int(in_last_30)
            selected.append({
                "source_ref": ref,
                "source_url": row["source_url"],
                "source_type": row.get("source_type"),
                "published_at": row.get("published_at"),
                "source_publication_age_days_from_unverified_metadata": source_age,
                "source_age_band": age_band,
                "inside_30_day_discovery_window": in_last_30,
                "publication_date_independently_verified": False,
                "source_must_be_checked_by_owner": True,
                "cross_topic_reused_reference": row.get("cross_topic_reused_reference") is True,
                "new_since_previous_refresh": new_to_previous,
                "already_present_in_previous_snapshot_not_reviewed": (
                    not new_to_previous if new_to_previous is not None else None
                ),
                "candidate_type": "UNVERIFIED_TITLE_MATCH_FOR_EDITORIAL_REVIEW",
                "suggested_owner_validation": "READ_SOURCE_THEN_VALIDATE_GSC_SERP_AND_SEARCH_INTENT",
            })
            review_first_count += 1
        review_topics.append({
            "topic": title,
            "original_reference_count": len(rows),
            "review_first_unverified_count": len(selected),
            "new_since_previous_refresh_count": topic_new if prior_refs is not None else None,
            "references_for_manual_review": selected,
            "relevance_verified": False,
            "search_demand_verified": False,
            "search_volume_or_rankings": None,
        })
    if total != handoff.get("source_observation_count"):
        raise ValueError("source_reference_count_mismatch")
    return {
        "schema_version": SCHEMA,
        "projection_revision": PROJECTION_REVISION,
        "status": "REVIEW_CITATIONS_READY" if review_first_count else "NO_TITLE_MATCHED_CITATIONS",
        "mode": "OWNER_REVIEW_ONLY",
        "generated_at": now.isoformat(),
        "source_handoff_generated_at": generated.astimezone(timezone.utc).isoformat(),
        "original_source_observation_count": total,
        "review_first_unique_citation_count": review_first_count,
        "source_age_review": {
            "date_authority": "UNVERIFIED_PUBLIC_SOURCE_METADATA",
            "age_calculated_in_utc_calendar_days": True,
            "active_in_last30_days_title_matches": fresh_review_count,
            "held_outside_window_or_invalid_date": review_first_count - fresh_review_count,
            "source_age_bands": source_age_counts,
            "older_citations_kept_for_audit_not_deleted": True,
            "expiry_never_implies_source_claim_invalid": True,
        },
        "delta_review": {
            "comparison_available": prior_refs is not None,
            "new_since_previous_refresh_count": new_count if prior_refs is not None else None,
            "already_present_previous_count": (review_first_count - new_count) if prior_refs is not None else None,
            "previously_seen_does_not_mean_human_reviewed": True,
            "novelty_refers_only_to_previous_snapshot_not_entire_history": True,
            "source_review_automatically_approved": False,
        },
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
    previous = None
    if target.exists():
        if not target.is_file() or target.stat().st_mode & 0o777 != 0o600:
            raise ValueError("untrusted_existing_private_review_file")
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            raise ValueError("unreadable_existing_private_review_file") from None
    result = build_seo_owner_review(handoff, now=now, previous=previous)
    # Preserve stable evidence/novelty classification for repeated refreshes
    # of the exact same source snapshot (e.g. retry during a Media OS run).
    if (previous is not None and previous.get("projection_revision") == PROJECTION_REVISION
            and previous.get("delta_review", {}).get("comparison_available") is not None
            and previous.get("source_handoff_generated_at") == result["source_handoff_generated_at"]
            and previous.get("original_source_observation_count") == result["original_source_observation_count"]
            and [
                (v.get("source_ref"), v.get("source_url"))
                for t in previous["topics"] for v in t["references_for_manual_review"]
            ] == [
                (v["source_ref"], v["source_url"])
                for t in result["topics"] for v in t["references_for_manual_review"]
            ]):
        result = dict(previous)
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if len(payload) > MAX_BYTES:
        raise ValueError("seo_review_payload_too_large")
    if previous is not None and target.read_bytes() == payload:
        return {
            "status": result["status"], "owner": result["owner"],
            "path": str(OUTPUT),
            "review_first_unique_citations": result["review_first_unique_citation_count"],
        "active_last30days_review_citations": result["source_age_review"]["active_in_last30_days_title_matches"],
        "held_old_or_undated_citations": result["source_age_review"]["held_outside_window_or_invalid_date"],
            "new_since_previous_refresh": result["delta_review"]["new_since_previous_refresh_count"],
            "prior_snapshot_comparison_available": result["delta_review"]["comparison_available"],
            "original_reference_count": result["original_source_observation_count"],
            "seo_code_modified": False, "no_automatic_publishing_or_indexing": True,
        }
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
        "active_last30days_review_citations": result["source_age_review"]["active_in_last30_days_title_matches"],
        "held_old_or_undated_citations": result["source_age_review"]["held_outside_window_or_invalid_date"],
        "new_since_previous_refresh": result["delta_review"]["new_since_previous_refresh_count"],
        "prior_snapshot_comparison_available": result["delta_review"]["comparison_available"],
        "original_reference_count": result["original_source_observation_count"],
        "seo_code_modified": False,
        "no_automatic_publishing_or_indexing": True,
    }
