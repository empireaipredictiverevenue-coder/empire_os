#!/usr/bin/env python3
"""Observe public Reddit/LinkedIn buyer pain and queue evidence signals."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from empire_os.community_intent import (
    collect_public_search_intent,
    enqueue_observation,
)
from empire_os.control_fabric import EventEnvelope, route_event
from empire_os.pain_solution_engine import build_pain_solution_briefs
from empire_os.search_fabric.search import search

OUTPUT = Path("/srv/empire_os/runtime/community_intent/latest.json")

QUERY_SETS = (
    ("reddit", "roofing", "DFW", (
        '"need more leads" roofing',
        '"struggling with" roofing leads',
        '"recommend" roofing marketing',
        '"hail" roofing leads',
    )),
    ("reddit", "b2b", "online", (
        '"struggling with" lead generation',
        '"looking for" sales automation',
        '"need" decision maker data',
        '"losing" leads follow up',
    )),
    ("linkedin", "b2b", "online", (
        '"looking for" lead generation',
        '"struggling with" sales pipeline',
        '"need" sales automation',
        '"looking for" SEO help',
        '"revenue growth" "looking for"',
    )),
)


def _search(query: str, limit: int):
    return search(query, num=limit)


def main() -> int:
    observations = []
    for platform, niche, metro, queries in QUERY_SETS:
        observations.extend(
            collect_public_search_intent(
                platform=platform,
                queries=queries,
                search_fn=_search,
                limit_per_query=6,
                metro=metro,
                niche=niche,
            )
        )

    results = [enqueue_observation(row) for row in observations]
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
        "schema_version": "empire.community_intent.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "execution_authority": "none",
        "outreach_authority": "none",
        "observations": len(observations),
        "high_intent": sum(row.intent_band == "high" for row in observations),
        "medium_intent": sum(row.intent_band == "medium" for row in observations),
        "by_source": dict(source_counts),
        "pain_points": dict(pain_counts.most_common()),
        "pain_solution_briefs": [row.as_dict() for row in pain_briefs],
        "control_fabric_routes": routed_pains,
        "signals": results,
        "top_observations": [
            row.as_dict() for row in observations[:20]
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
