#!/usr/bin/env python3
"""Observe public Reddit/LinkedIn buyer pain and queue evidence signals."""
from __future__ import annotations

import json
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
from empire_os.search_fabric.search import search

ROOT = Path("/srv/empire_os")
OUTPUT = ROOT / "runtime/community_intent/latest.json"
HISTORY = ROOT / "runtime/community_intent/observations.json"

# Exactly one Reddit and one LinkedIn search are attempted per cycle.
# The 15-minute timer rotates the search so we do not hammer providers.
REDDIT_ROTATION = (
    ("sales", "lead generation", "b2b", "online"),
    ("smallbusiness", "marketing leads", "b2b", "online"),
    ("Entrepreneur", "sales automation", "b2b", "online"),
    ("marketing", "lead generation", "b2b", "online"),
    ("SEO", "seo leads", "search", "online"),
    ("Roofing", "roofing leads", "roofing", "DFW"),
)

LINKEDIN_ROTATION = (
    ('"struggling with" sales pipeline', "b2b", "online"),
    ('"looking for" sales automation', "b2b", "online"),
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
    payload = search(
        f"site:linkedin.com/posts {query}",
        num=8,
    )
    engine = (payload.get("searchParameters") or {}).get("engine")
    error = payload.get("error")
    rows: list[IntentObservation] = []
    for result in payload.get("organic") or []:
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
        "ok": not bool(error),
        "engine": engine,
        "error": error,
        "result_count": len(payload.get("organic") or []),
        "accepted_observations": len(rows),
        "query": query,
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    slot = int(now.timestamp() // (15 * 60))

    subreddit, reddit_query, reddit_niche, reddit_metro = (
        REDDIT_ROTATION[slot % len(REDDIT_ROTATION)]
    )
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
    existing = _load_history()
    observations = _merge_window(existing, current, now=now)

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
        "new_observations": len(current),
        "high_intent": sum(
            row.intent_band == "high" for row in observations
        ),
        "medium_intent": sum(
            row.intent_band == "medium" for row in observations
        ),
        "by_source": dict(source_counts),
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
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
