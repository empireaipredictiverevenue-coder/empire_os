"""Community intent and pain-point intelligence for EmpireOS.

This module turns public Reddit/LinkedIn observations into evidence-bearing
signals. It does not create canonical prospects, send outreach, scrape private
content, or infer revenue.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

import requests

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
    re.compile(r"\b(budget|quote|rfp|switching|replace)\b", re.I),
    re.compile(r"\b(losing|wasting).{0,24}\b(time|money|revenue|leads)\b", re.I),
    re.compile(r"\bhow (do|can) (i|we).{0,40}\b(scale|automate|grow|find|get)\b", re.I),
)

EMPLOYMENT_PATTERNS = (
    re.compile(r"\bwe(?:'re| are) hiring\b", re.I),
    re.compile(r"\bjoin our team\b", re.I),
    re.compile(r"\bjob opening\b", re.I),
    re.compile(r"\bapply (?:now|today|here)\b", re.I),
    re.compile(r"\binside sales representative\b", re.I),
    re.compile(r"\boutside sales (?:representative|account manager)\b", re.I),
    re.compile(r"\bopen role\b", re.I),
    re.compile(r"\bcareer opportunity\b", re.I),
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

_HTML_TAG = re.compile(r"<[^>]+>")
_REDDIT_UA = "EmpireOS/1.0 (+https://empire-ai.co.uk)"


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
    if source == "linkedin" and any(
        pattern.search(text) for pattern in EMPLOYMENT_PATTERNS
    ):
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


def parse_reddit_atom(
    xml_text: str,
    *,
    query: str,
    niche: str = "b2b",
    metro: str = "online",
) -> list[IntentObservation]:
    """Parse public Reddit Atom search results into signal-only observations."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns = {"a": "http://www.w3.org/2005/Atom"}
    rows: list[IntentObservation] = []
    seen: set[str] = set()

    for entry in root.findall("a:entry", ns):
        title = _clean(entry.findtext("a:title", default="", namespaces=ns))
        author = _clean(
            entry.findtext("a:author/a:name", default="", namespaces=ns)
        )
        observed_at = _clean(
            entry.findtext("a:updated", default="", namespaces=ns)
            or entry.findtext("a:published", default="", namespaces=ns)
        )
        content = entry.findtext("a:content", default="", namespaces=ns)
        summary = entry.findtext("a:summary", default="", namespaces=ns)
        body = _clean(_HTML_TAG.sub(" ", content or summary or ""))

        url = ""
        for link in entry.findall("a:link", ns):
            href = _clean(link.attrib.get("href"))
            rel = _clean(link.attrib.get("rel") or "alternate")
            if href and rel in {"alternate", ""}:
                url = href
                break
        if not url:
            url = _clean(entry.findtext("a:id", default="", namespaces=ns))
        if not url or "reddit.com" not in url.lower() or url in seen:
            continue

        combined = _clean(f"{title} {body}")
        if not combined:
            continue
        score, band = score_intent(combined)
        pain_points = classify_pain_points(combined)
        if band == "low" and not pain_points:
            continue

        seen.add(url)
        rows.append(
            IntentObservation(
                source="reddit",
                url=url,
                title=title,
                text=body[:700],
                author=author,
                observed_at=(
                    observed_at
                    or datetime.now(timezone.utc).isoformat()
                ),
                query=_clean(query),
                metro=_clean(metro),
                niche=_clean(niche),
                pain_points=pain_points,
                intent_score=score,
                intent_band=band,
            )
        )

    rows.sort(key=lambda item: (-item.intent_score, item.url))
    return rows


def collect_reddit_rss_intent(
    *,
    subreddit: str,
    query: str,
    niche: str = "b2b",
    metro: str = "online",
    timeout: int = 15,
    get_fn: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Fetch exactly one public Reddit Atom search feed.

    One request per cycle keeps the observer polite. 429/403 is reported as
    source health rather than converted into a false zero-demand signal.
    """
    sub = re.sub(r"[^A-Za-z0-9_]+", "", str(subreddit or ""))
    if not sub:
        raise ValueError("subreddit required")
    url = f"https://www.reddit.com/r/{sub}/search.rss"
    try:
        response = get_fn(
            url,
            params={
                "q": query,
                "restrict_sr": "on",
                "sort": "new",
                "t": "week",
            },
            headers={
                "User-Agent": _REDDIT_UA,
                "Accept": "application/atom+xml,application/rss+xml,text/xml",
            },
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "reason": f"request_failed:{type(exc).__name__}",
            "observations": [],
            "subreddit": sub,
            "query": query,
        }

    status = int(getattr(response, "status_code", 0) or 0)
    content_type = str(
        getattr(response, "headers", {}).get("content-type", "")
    ).lower()
    if status != 200:
        return {
            "ok": False,
            "status_code": status,
            "reason": "rate_limited" if status == 429 else f"http_{status}",
            "observations": [],
            "subreddit": sub,
            "query": query,
        }
    if "xml" not in content_type and "atom" not in content_type:
        return {
            "ok": False,
            "status_code": status,
            "reason": "unexpected_content_type",
            "observations": [],
            "subreddit": sub,
            "query": query,
        }

    observations = parse_reddit_atom(
        str(getattr(response, "text", "") or ""),
        query=query,
        niche=niche,
        metro=metro,
    )
    return {
        "ok": True,
        "status_code": status,
        "reason": None,
        "observations": observations,
        "subreddit": sub,
        "query": query,
    }


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
