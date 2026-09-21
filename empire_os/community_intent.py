"""Community intent and pain-point intelligence for EmpireOS.

This module turns public Reddit/LinkedIn observations into evidence-bearing
signals. It does not create canonical prospects, send outreach, scrape private
content, or infer revenue.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from empire_os.candidate_quality import assess_candidate
from empire_os.lead_sources import LeadCandidate
from empire_os.signal_inbox import enqueue_signal


PLATFORM_DOMAINS = {
    "reddit": ("reddit.com", "old.reddit.com"),
    "linkedin": ("linkedin.com",),
}

INTENT_PATTERNS = (
    re.compile(r"\b(need|looking for|searching for|seeking)\b", re.I),
    re.compile(r"\b(recommend|recommendation|anyone using|what tool|which tool)\b", re.I),
    re.compile(r"\b(struggling|frustrated|stuck|pain point|problem with)\b", re.I),
    re.compile(r"\b(hiring|budget|quote|rfp|switching|replace)\b", re.I),
    re.compile(r"\b(losing|wasting).{0,24}\b(time|money|revenue|leads)\b", re.I),
    re.compile(r"\bhow (do|can) (i|we).{0,40}\b(scale|automate|grow|find|get)\b", re.I),
)

PAIN_TAXONOMY: dict[str, tuple[re.Pattern[str], ...]] = {
    "lead_generation": (
        re.compile(r"\b(leads?|pipeline|appointments?|prospects?)\b", re.I),
        re.compile(r"\b(get|find|generate).{0,20}\b(customers?|clients?)\b", re.I),
    ),
    "sales_conversion": (
        re.compile(r"\b(close|closing|conversion|convert|follow.?up|ghosted)\b", re.I),
        re.compile(r"\b(sales process|sales team|crm)\b", re.I),
    ),
    "search_visibility": (
        re.compile(r"\b(seo|rank|ranking|google maps|search traffic|organic traffic)\b", re.I),
        re.compile(r"\b(not showing|not visible|visibility)\b", re.I),
    ),
    "automation_ops": (
        re.compile(r"\b(manual|spreadsheet|time consuming|repetitive|automate|automation)\b", re.I),
        re.compile(r"\b(workflow|integration|operations?)\b", re.I),
    ),
    "data_intelligence": (
        re.compile(r"\b(decision.?maker|contact data|enrichment|market research|intent data)\b", re.I),
        re.compile(r"\b(find|identify).{0,20}\b(owner|buyer|company|companies)\b", re.I),
    ),
    "revenue_growth": (
        re.compile(r"\b(revenue|mrr|arr|growth|profit|margin|cac|ltv|churn)\b", re.I),
        re.compile(r"\b(growth stalled|plateau|losing money)\b", re.I),
    ),
    "storm_demand": (
        re.compile(r"\b(hail|storm|wind damage|roof damage|restoration)\b", re.I),
        re.compile(r"\b(storm leads?|insurance claims?|catastrophe)\b", re.I),
    ),
}


@dataclass(frozen=True)
class IntentObservation:
    source: str
    url: str
    title: str
    text: str
    author: str = ""
    observed_at: str = ""
    engagement: int = 0
    query: str = ""
    metro: str = ""
    niche: str = ""
    pain_points: tuple[str, ...] = ()
    intent_score: int = 0
    intent_band: str = "low"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def classify_pain_points(text: str) -> tuple[str, ...]:
    value = _clean(text)
    labels = []
    for label, patterns in PAIN_TAXONOMY.items():
        if any(pattern.search(value) for pattern in patterns):
            labels.append(label)
    return tuple(labels)


def score_intent(text: str, *, engagement: int = 0) -> tuple[int, str]:
    value = _clean(text)
    intent_hits = sum(1 for pattern in INTENT_PATTERNS if pattern.search(value))
    pain_count = len(classify_pain_points(value))
    score = min(
        100,
        intent_hits * 18
        + pain_count * 10
        + min(max(int(engagement), 0), 50) // 5,
    )
    band = "high" if score >= 60 else "medium" if score >= 35 else "low"
    return score, band


def normalize_search_result(
    *,
    platform: str,
    query: str,
    result: Mapping[str, Any],
    metro: str = "",
    niche: str = "",
) -> IntentObservation | None:
    source = str(platform or "").strip().lower()
    domains = PLATFORM_DOMAINS.get(source)
    if not domains:
        raise ValueError("unsupported community platform")

    url = _clean(result.get("link") or result.get("url"))
    if not url or not any(domain in url.lower() for domain in domains):
        return None

    title = _clean(result.get("title"))
    snippet = _clean(result.get("snippet") or result.get("text"))
    text = _clean(f"{title} {snippet}")
    if not text:
        return None

    score, band = score_intent(text)
    pain_points = classify_pain_points(text)
    if band == "low" and not pain_points:
        return None

    return IntentObservation(
        source=source,
        url=url,
        title=title,
        text=snippet,
        observed_at=datetime.now(timezone.utc).isoformat(),
        query=_clean(query),
        metro=_clean(metro),
        niche=_clean(niche),
        pain_points=pain_points,
        intent_score=score,
        intent_band=band,
    )


def observation_to_signal(observation: IntentObservation) -> LeadCandidate:
    pain = ",".join(observation.pain_points) or "unclassified"
    return LeadCandidate(
        name=f"{observation.source} intent signal",
        niche=observation.niche or "commercial_intent",
        metro=observation.metro or "online",
        details=(
            f"Public {observation.source} intent observation; "
            f"intent_band={observation.intent_band}; pain_points={pain}; "
            f"title={observation.title[:180]}"
        ),
        source=f"{observation.source}_intent",
        lead_score=observation.intent_score,
        url=observation.url,
        raw={
            "community_intent": observation.as_dict(),
            "entity_kind": "signal",
            "outreach_authority": "none",
        },
    )


def enqueue_observation(observation: IntentObservation) -> dict[str, Any]:
    candidate = observation_to_signal(observation)
    quality = assess_candidate(candidate)
    result = enqueue_signal(candidate, quality=quality)
    return {
        **result,
        "intent_score": observation.intent_score,
        "intent_band": observation.intent_band,
        "pain_points": list(observation.pain_points),
        "outreach_authority": "none",
    }


def collect_public_search_intent(
    *,
    platform: str,
    queries: Iterable[str],
    search_fn: Callable[[str, int], Mapping[str, Any]],
    limit_per_query: int = 8,
    metro: str = "",
    niche: str = "",
) -> list[IntentObservation]:
    observations: list[IntentObservation] = []
    seen: set[str] = set()
    domain = PLATFORM_DOMAINS[platform][0]

    for query in queries:
        search_query = f"site:{domain} {query}"
        payload = search_fn(search_query, limit_per_query)
        for result in payload.get("organic") or []:
            if not isinstance(result, Mapping):
                continue
            observation = normalize_search_result(
                platform=platform,
                query=query,
                result=result,
                metro=metro,
                niche=niche,
            )
            if observation is None or observation.url in seen:
                continue
            seen.add(observation.url)
            observations.append(observation)

    observations.sort(
        key=lambda item: (-item.intent_score, item.source, item.url)
    )
    return observations
