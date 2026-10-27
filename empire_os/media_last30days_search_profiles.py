"""Keyless source-query profiles for the four approved Last30Days topics.

Never invent source evidence or return buyer/search demand claims. This only
chooses a more specific, single public-source query for the existing
quick/one-topic Media OS cycle.
"""
from __future__ import annotations

import json
from typing import Any

SEARCH_BY_TOPIC: dict[str, str] = {
    "AI lead generation for roofing contractors": "roofing contractor lead generation",
    "AI agents for small businesses": "AI agents small business automation",
    "AI sales avatars and digital sales agents": "AI sales agents appointment setting",
    "first-party revenue intelligence and attribution": "marketing attribution revenue tracking",
}

def plan_for_approved_topic(topic: str) -> dict[str, Any]:
    if type(topic) is not str or topic not in SEARCH_BY_TOPIC:
        raise ValueError("unapproved_last30days_research_topic")
    return {
        "intent": "concept",
        "freshness_mode": "recent",
        "cluster_mode": "none",
        "subqueries": [{
            "label": "bounded-topic-discovery",
            "search_query": SEARCH_BY_TOPIC[topic],
            "ranking_query": topic,
            "sources": ["reddit", "hackernews"],
            "weight": 1.0,
        }],
        "source_weights": {"reddit": 1.0, "hackernews": 1.0},
        "notes": ["owner-scoped-last30days", "topical-proposals-not-search-volume"],
    }

def plan_json(topic: str) -> str:
    return json.dumps(plan_for_approved_topic(topic), sort_keys=True, separators=(",", ":"))

# Production policy: the other candidates are research experiments only.
# Roofing was the sole topic that improved in bounded live title-relevance QA.
ENABLED_TOPIC_PROFILES = frozenset({"AI lead generation for roofing contractors"})

def enabled_plan_json(topic: str) -> str | None:
    if topic not in SEARCH_BY_TOPIC:
        raise ValueError("unapproved_last30days_research_topic")
    return plan_json(topic) if topic in ENABLED_TOPIC_PROFILES else None
