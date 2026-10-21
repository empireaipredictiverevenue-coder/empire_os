#!/usr/bin/env python3
"""Observe public Reddit/LinkedIn buyer pain and queue evidence signals."""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from empire_os.community_intent import (
    IntentObservation,
    collect_reddit_rss_intent,
    enqueue_observation,
    normalize_search_result,
)
from empire_os.control_fabric import EventEnvelope, route_event
from empire_os.pain_solution_engine import build_pain_solution_briefs
from empire_os.jev_client_pain_discovery import discover_client_pains
from empire_os.search_fabric.reliable_search import search_reliable
from empire_os.icp_intent_source_atlas import (
    REDDIT_ROTATION as ICP_REDDIT_ROTATION,
    atlas_summary,
)

from empire_os.community_intent_learning import (
    load_history as load_source_learning,
    record_episode,
    select_source,
    snapshot as source_learning_snapshot,
    write_snapshot as write_source_learning,
)

ROOT = Path("/srv/empire_os")
OUTPUT = ROOT / "runtime/community_intent/latest.json"
HISTORY = ROOT / "runtime/community_intent/observations.json"
LEARNING = ROOT / "runtime/community_intent/source_learning_latest.json"

# Exactly one Reddit and one LinkedIn search are attempted per cycle.
# The 15-minute timer rotates the search so we do not hammer providers.
# Priority first-party ICP communities plus cross-industry signal coverage.
# Exactly one public Reddit RSS query per existing 15-minute timer tick.
REDDIT_ROTATION = ICP_REDDIT_ROTATION + (
    ("sales", "lead generation", "b2b", "online"),
    ("sales", "sales pipeline", "b2b", "online"),
    ("solar", "need more leads", "solar", "US"),
)


LINKEDIN_ROTATION = (
    ('"looking for" sales automation', "b2b", "online"),
    ('"struggling with" sales pipeline', "b2b", "online"),
    ('"need" lead generation', "b2b", "online"),
    ('"looking for" SEO help', "search", "online"),
    ('"manual" follow up leads', "b2b", "online"),
    ('"revenue growth" pipeline', "b2b", "online"),
)


def _load_history() -> list[IntentObservation]:
    try:
        payload = json.loads(HISTORY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("observations") if isinstance(payload, dict) else []
    output: list[IntentObservation] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            output.append(IntentObservation(
                source=str(row.get("source") or ""),
                url=str(row.get("url") or ""),
                title=str(row.get("title") or ""),
                text=str(row.get("text") or ""),
                author=str(row.get("author") or ""),
                observed_at=str(row.get("observed_at") or ""),
                engagement=int(row.get("engagement") or 0),
                query=str(row.get("query") or ""),
                metro=str(row.get("metro") or ""),
                niche=str(row.get("niche") or ""),
                pain_points=tuple(row.get("pain_points") or ()),
                intent_score=int(row.get("intent_score") or 0),
                intent_band=str(row.get("intent_band") or "low"),
                evidence_urls=tuple(row.get("evidence_urls") or ()),
            ))
        except (TypeError, ValueError):
            continue
    return output


def _observed_time(row: IntentObservation) -> datetime | None:
    try:
        value = datetime.fromisoformat(
            row.observed_at.replace("Z", "+00:00")
        )
    except (AttributeError, ValueError):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _merge_window(
    existing: list[IntentObservation],
    current: list[IntentObservation],
    *,
    now: datetime,
    hours: int = 48,
) -> list[IntentObservation]:
    cutoff = now - timedelta(hours=hours)
    merged: dict[str, IntentObservation] = {}
    for row in existing:
        observed = _observed_time(row)
        if not row.url or observed is None or observed < cutoff:
            continue
        merged[row.url] = row
    for row in current:
        if not row.url:
            continue
        # Preserve first-seen timestamp when a web-search result repeats.
        if row.url in merged:
            prior = merged[row.url]
            merged[row.url] = IntentObservation(
                source=row.source,
                url=row.url,
                title=row.title or prior.title,
                text=row.text or prior.text,
                author=row.author or prior.author,
                observed_at=prior.observed_at,
                engagement=max(row.engagement, prior.engagement),
                query=row.query or prior.query,
                metro=row.metro or prior.metro,
                niche=row.niche or prior.niche,
                pain_points=row.pain_points or prior.pain_points,
                intent_score=max(row.intent_score, prior.intent_score),
                intent_band=(
                    row.intent_band
                    if row.intent_score >= prior.intent_score
                    else prior.intent_band
                ),
                evidence_urls=tuple(dict.fromkeys([
                    *prior.evidence_urls,
                    *row.evidence_urls,
                ])),
            )
        else:
            merged[row.url] = row
    return sorted(
        merged.values(),
        key=lambda item: (-item.intent_score, item.source, item.url),
    )


def _collect_linkedin(
    query: str,
    niche: str,
    metro: str,
) -> tuple[list[IntentObservation], dict]:
    # The search reliability layer enforces a persistent provider circuit:
    # no multi-engine retry storm every 15 minutes when public providers
    # return blocks. Historical cached results must NEVER become a new
    # observation (social-post publication dates are not authenticated).
    payload = search_reliable(
        f"site:linkedin.com/posts {query}",
        num=5,
        use_cache=False,
    )
    params = payload.get("searchParameters") or {}
    engine = params.get("engine")
    freshness_verified = (
        not payload.get("error")
        and params.get("search_state") == "RESULTS"
        and not any(params.get(name) for name in (
            "cache", "memory_cache", "stale_cache",
        ))
        and payload.get("organic") is not None
    )
    error = payload.get("error") or (
        None if freshness_verified else "PROVIDER_UNAVAILABLE_OR_CACHED"
    )
    rows: list[IntentObservation] = []
    for result in (payload.get("organic") or []) if freshness_verified else []:
        if not isinstance(result, dict):
            continue
        observation = normalize_search_result(
            platform="linkedin",
            query=query,
            result=result,
            metro=metro,
            niche=niche,
        )
        if observation is not None:
            rows.append(observation)
    return rows, {
        "ok": freshness_verified,
        "engine": engine,
        "error": error,
        "search_state": params.get("search_state"),
        "search_operational_status": payload.get("search_operational_status"),
        "circuit_open": bool(params.get("circuit_open")),
        "cached_results_rejected_as_live": bool(
            params.get("cache") or params.get("stale_cache")
            or params.get("memory_cache")
        ),
        "result_count": len(payload.get("organic") or []) if freshness_verified else 0,
        "accepted_observations": len(rows),
        "query": query,
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    slot = int(now.timestamp() // (15 * 60))

    previous_learning = load_source_learning(LEARNING)
    selected_source = select_source(
        REDDIT_ROTATION, previous_learning, slot=slot
    )
    subreddit, reddit_query, reddit_niche, reddit_metro = selected_source
    previous_observations = _load_history()
    previous_urls = {row.url for row in previous_observations}
    reddit = collect_reddit_rss_intent(
        subreddit=subreddit,
        query=reddit_query,
        niche=reddit_niche,
        metro=reddit_metro,
    )
    reddit_rows = list(reddit.get("observations") or [])

    linkedin_query, linkedin_niche, linkedin_metro = (
        LINKEDIN_ROTATION[slot % len(LINKEDIN_ROTATION)]
    )
    linkedin_rows, linkedin_status = _collect_linkedin(
        linkedin_query,
        linkedin_niche,
        linkedin_metro,
    )

    current = reddit_rows + linkedin_rows
    observations = _merge_window(previous_observations, current, now=now)
    learned_episodes, learning_episode = record_episode(
        previous_learning,
        source=selected_source,
        slot=slot,
        retrieval_ok=reddit.get("ok") is True,
        observations=reddit_rows,
        previously_observed_urls=previous_urls,
        now=now,
    )
    next_research_source = select_source(
        REDDIT_ROTATION, learned_episodes, slot=slot+1
    )
    learning = source_learning_snapshot(
        learned_episodes, REDDIT_ROTATION,
        now=now, latest=learning_episode, next_source=next_research_source,
    )

    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    history_tmp = HISTORY.with_suffix(".json.tmp")
    history_tmp.write_text(json.dumps({
        "schema_version": "empire.community_intent_history.v1",
        "updated_at": now.isoformat(),
        "window_hours": 48,
        "observations": [row.as_dict() for row in observations],
    }, indent=2, sort_keys=True) + "\n")
    history_tmp.replace(HISTORY)

    current_urls = {row.url for row in current}
    results = [
        enqueue_observation(row)
        for row in observations
        if row.url in current_urls
    ]

    pain_briefs = build_pain_solution_briefs(observations)
    # Shadow Jev client-pain review: same observations, no extra search/API,
    # no buyer identity promotion, CRM mutation, messaging or revenue actions.
    jev_pain_review = discover_client_pains(
        [row.as_dict() for row in observations],
        now=now,
        include_private_source_links=True,
    )
    routed_pains = []
    for brief in pain_briefs:
        if brief.opportunity_event is None:
            continue
        event = EventEnvelope(
            event_type="community_pain_observed",
            source="community_intent",
            subject_id=brief.pain_point,
            payload={
                "pain_point": brief.pain_point,
                "offer_key": brief.offer_key,
                "products": list(brief.products),
                "evidence_strength": brief.evidence_strength,
                "observed_mentions": brief.observed_mentions,
                "average_intent_score": brief.average_intent_score,
            },
            evidence_refs=tuple(brief.evidence_urls),
            commercial_priority=min(
                100,
                round(brief.average_intent_score)
                + min(brief.observed_mentions * 3, 20),
            ),
        )
        routed_pains.append({
            "event": event.as_dict(),
            "routes": route_event(event),
        })

    pain_counts = Counter(
        pain for row in observations for pain in row.pain_points
    )
    source_counts = Counter(row.source for row in observations)
    payload = {
        "schema_version": "empire.community_intent.v2",
        "observed_at": now.isoformat(),
        "window_hours": 48,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "outreach_authority": "none",
        "observations": len(observations),
        "new_observations": len({
            row.url for row in current if row.url not in previous_urls
        }),
        "fetched_observations": len(current),
        "icp_research_learning": {
            "schema_version": learning["schema_version"],
            "episode_count": learning["episode_count"],
            "latest_source": learning_episode["source_id"],
            "new_source_posts": learning_episode["unique_new_posts"],
            "next_research_task": learning["next_research_task"],
            "next_research_source": learning["next_research_source"],
            "learning_scope": learning["learning_scope"],
            "actual_revenue_learning": learning["actual_revenue_learning"],
            "execution_authority": "NONE",
        },
        "high_intent": sum(
            row.intent_band == "high" for row in observations
        ),
        "identity_seed_ready": sum(
            bool(row.evidence_urls) for row in observations
        ),
        "medium_intent": sum(
            row.intent_band == "medium" for row in observations
        ),
        "by_source": dict(source_counts),
        "icp_source_atlas": atlas_summary(),
        "source_status": {
            "reddit": {
                "ok": reddit.get("ok"),
                "status_code": reddit.get("status_code"),
                "reason": reddit.get("reason"),
                "subreddit": subreddit,
                "query": reddit_query,
                "accepted_observations": len(reddit_rows),
            },
            "linkedin": linkedin_status,
        },
        "pain_points": dict(pain_counts.most_common()),
        "jev_client_pain_discovery": {
            key: value for key, value in jev_pain_review.items()
            if key != "items"
        },
        "pain_solution_briefs": [
            row.as_dict() for row in pain_briefs
        ],
        "control_fabric_routes": routed_pains,
        "signals": results,
        "top_observations": [
            row.as_dict() for row in observations[:20]
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # The private founder queue retains the public evidence URL so Research can
    # independently inspect it. It is gitignored and permission restricted.
    # Never include the individual source links in the normal cycle payload.
    private_queue = OUTPUT.parent / "jev_client_pain_review_latest.json"
    fd, tmp_private = tempfile.mkstemp(
        prefix=".jev_pain_", suffix=".tmp", dir=OUTPUT.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(jev_pain_review, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(tmp_private, private_queue)
    finally:
        if os.path.exists(tmp_private):
            os.unlink(tmp_private)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    tmp.replace(OUTPUT)
    write_source_learning(LEARNING, learning)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
