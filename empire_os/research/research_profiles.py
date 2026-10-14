"""EmpireOS research profiles and declarative, fail-closed step receipts.

Independent design informed by Vane's mode/source choices and OpenManus's
plan-step lifecycle. No upstream code is copied and no tools execute here
except explicitly injected, governed search/inspection callbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Mapping, Sequence

from .deep_research_intake import ResearchLimits, run_research

_ALLOWED_LANES = frozenset({"web", "official", "community", "academic", "company"})
_PROFILES: dict[str, ResearchLimits] = {
    "speed": ResearchLimits(max_queries=2, max_rounds=1, results_per_query=3, max_pages=4),
    "balanced": ResearchLimits(max_queries=4, max_rounds=2, results_per_query=4, max_pages=8),
    "quality": ResearchLimits(max_queries=8, max_rounds=3, results_per_query=5, max_pages=12),
}


@dataclass(frozen=True)
class ResearchProfile:
    mode: str = "balanced"
    lanes: tuple[str, ...] = ("web", "official", "community")
    country: str = "GB"
    sector: str = ""

    def validate(self) -> ResearchLimits:
        if self.mode not in _PROFILES:
            raise ValueError("unsupported research depth")
        if not self.lanes or len(self.lanes) > 5:
            raise ValueError("provide between one and five evidence lanes")
        if len(set(self.lanes)) != len(self.lanes):
            raise ValueError("duplicate research lane")
        if any(lane not in _ALLOWED_LANES for lane in self.lanes):
            raise ValueError("unsupported research lane")
        if self.country not in {"GB", "US", "CA", "AU", "GLOBAL"}:
            raise ValueError("unsupported research country")
        return _PROFILES[self.mode]


def _clean(value: Any, length: int) -> str:
    return " ".join(str(value or "").split())[:length]


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _has_phrase(haystack: str, needle: str) -> bool:
    words, required = _tokens(haystack), _tokens(needle)
    return bool(required) and any(
        words[i:i + len(required)] == required
        for i in range(len(words) - len(required) + 1)
    )


def _lane_query(base: str, lane: str, country: str) -> str:
    """Intent-targeted public discovery; never direct unauthorised scraping."""
    jurisdiction = {
        "GB": "UK", "US": "US", "CA": "Canada", "AU": "Australia", "GLOBAL": "",
    }[country]
    already_local = (
        _has_phrase(base, jurisdiction)
        or (country == "US" and _has_phrase(base, "USA"))
        or (country == "GB" and _has_phrase(base, "United Kingdom"))
    )
    prefix = _clean(base if already_local else " ".join((base, jurisdiction)), 220)
    suffix = {
        "web": "market evidence",
        "official": "official primary source government public data",
        "community": "site:reddit.com discussion problems unmet needs",
        "academic": "published research study systematic review",
        "company": (
            "publisher affiliate application partner program"
            if any(word in _tokens(base) for word in (
                "buyer", "buyers", "leads", "publisher", "publishers", "affiliate", "roofing", "solar"
            )) else "company website case study pricing public announcement"
        ),
    }[lane]
    return _clean(f"{prefix} {suffix}", 270)


def build_research_plan(question: str, profile: ResearchProfile) -> dict[str, Any]:
    limits = profile.validate()
    subject = _clean(question, 180)
    if not subject:
        raise ValueError("research question is required")
    sector = _clean(profile.sector, 50)
    topic = _clean(
        subject if not sector or _has_phrase(subject, sector)
        else " ".join((subject, sector)), 220
    )
    queries = [topic]
    for lane in profile.lanes:
        q = _lane_query(topic, lane, profile.country)
        if q.casefold() not in {v.casefold() for v in queries}:
            queries.append(q)
    # Reserve available queries for evidence-gap followups where possible.
    cap = min(limits.max_queries, 1 + len(profile.lanes))
    selected = queries[:cap]
    steps = [
        {"id": "plan", "purpose": "Formulate a scoped research question", "status": "ready"},
        {"id": "discover", "purpose": "Gather bounded public search observations", "status": "not_started"},
        {"id": "inspect", "purpose": "Inspect original source documents safely", "status": "not_started"},
        {"id": "crosscheck", "purpose": "Find contradictions and evidence gaps", "status": "not_started"},
        {"id": "synthesize", "purpose": "Draft claims tied to inspected source IDs", "status": "not_started"},
        {"id": "commercial", "purpose": "Separate research from verified commercial authority", "status": "blocked"},
    ]
    return {
        "schema_version": "empire.research_plan.profile.v1",
        "status": "PLANNED_ONLY",
        "mode": "OBSERVE",
        "profile": profile.mode,
        "lanes": list(profile.lanes),
        "country": profile.country,
        "sector": sector,
        "question": subject,
        "queries": selected,
        "limits": {
            "max_queries": limits.max_queries,
            "max_rounds": limits.max_rounds,
            "results_per_query": limits.results_per_query,
            "max_pages": limits.max_pages,
        },
        "steps": steps,
        "execution_authority": "none",
        "outbound_authorized": False,
        "database_write": False,
    }


def research_with_profile(
    question: str,
    *,
    profile: ResearchProfile,
    search_fn: Callable[..., Mapping[str, Any]],
    inspect_fn: Callable[[str], Mapping[str, Any]],
    follow_up_fn: Callable[[str, list[dict[str, Any]], list[str]], Sequence[str]] | None = None,
    synthesize_fn: Callable[[str, list[dict[str, Any]]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute only explicitly supplied public search/inspection callbacks.

    A step receipt describes evidence handling, not independently verified
    facts, buyer intent, contact qualification, business outcome or deployment.
    """
    plan = build_research_plan(question, profile)
    limits = profile.validate()
    evidence = run_research(
        question,
        search_fn=search_fn,
        inspect_fn=inspect_fn,
        limits=limits,
        initial_queries=plan["queries"],
        follow_up_fn=follow_up_fn,
        synthesize_fn=synthesize_fn,
    )
    received = evidence["source_count"]
    inspected = evidence["original_pages_inspected"]
    drafts = len(evidence["draft_claims"])
    states = {
        "plan": "completed",
        "discover": "observed" if evidence["budget"]["searches_executed"] else "blocked",
        "inspect": "observed" if inspected else "blocked",
        "crosscheck": "pending_evidence_review" if received else "blocked",
        "synthesize": "draft_ready" if drafts else ("pending_model" if inspected else "blocked"),
        "commercial": "blocked",
    }
    receipt = dict(plan)
    receipt["status"] = evidence["status"]
    receipt["steps"] = [
        {**step, "status": states[step["id"]]} for step in plan["steps"]
    ]
    receipt["evidence"] = evidence
    receipt["claimed_commercial_authority"] = False
    return receipt
