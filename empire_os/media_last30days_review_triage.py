"""Deterministic, conservative review triage for Last30Days citation titles.

No model inference, buyer score, commercial claim, or external network call.
A title-anchor match only means 'read this citation first', NEVER verified topic
relevance. Full raw observations stay in the original Media OS research queue.
"""
from __future__ import annotations

import re
from typing import Any

# Paired anchors, not broad single words such as 'AI', 'lead', or 'revenue'.
# High precision is intentional; false negatives stay in context-only review.
_TITLE_ANCHORS = {
    "AI lead generation for roofing contractors": (
        (r"\broof(?:ing|ers?|s)?\b", r"\b(?:lead|contractor|call|marketing|customer|sales|appointment)s?\b"),
    ),
    "AI agents for small businesses": (
        (r"\b(?:agents?|automat\w*|autonomous)\b", r"\b(?:business(?:es)?|small\s+business(?:es)?|smbs?|entrepreneur\w*|office|owners?)\b"),
    ),
    "AI sales avatars and digital sales agents": (
        (r"\b(?:sales|selling|seller|outbound|prospecting)\b", r"\b(?:agent\w*|avatars?|virtual|digital|voice|ai)\b"),
    ),
    "first-party revenue intelligence and attribution": (
        (r"\b(?:revenues?|attribution|attributed|conversions?|ltv|roi|customer\s+acquisition)\b",
         r"\b(?:first.party|data|analytics|intelligence|predict\w*|tracking|measur\w*|marketing|revenue)\b"),
    ),
}
MAX_TITLE_LENGTH = 150


def title_topic_match_candidate(topic: Any, title: Any) -> bool:
    """Return conservative *unverified* title match. Never use for automation."""
    if (not isinstance(topic, str) or topic not in _TITLE_ANCHORS
            or not isinstance(title, str) or not 5 <= len(title) <= MAX_TITLE_LENGTH):
        return False
    lowered = title.casefold()
    return any(
        re.search(a, lowered, flags=re.ASCII) and re.search(b, lowered, flags=re.ASCII)
        for a, b in _TITLE_ANCHORS[topic]
    )


TRIAGE_METHOD = "TWO_TOPIC_TITLE_ANCHORS_HEURISTIC_UNVERIFIED"
REVIEW_FIRST = "READ_TITLE_MATCH_FIRST_REQUIRES_HUMAN_CHECK"
CONTEXT_ONLY = "CONTEXT_ONLY_WEAK_OR_OFF_TOPIC_TITLE"
