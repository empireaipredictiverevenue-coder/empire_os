"""Typed V2 classification for public community-intent observations.

Deterministic and OBSERVE-only. Public text may support an inferred commercial
intent classification, but it cannot establish canonical buyer intent, company
identity, willingness to pay, revenue, or outreach authority.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


INTENT_TAXONOMY: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "DEMAND_SHORTAGE": (
        ("need_more_leads", _rx(
            r"\b(need|want|looking for|trying to get).{0,24}\b(more )?"
            r"(leads?|customers?|clients?|appointments?|jobs?)\b"
        )),
        ("not_enough_jobs", _rx(
            r"\b(not enough|need more|short on|slow).{0,20}\b"
            r"(jobs?|work|bookings?)\b"
        )),
        ("pipeline_dry", _rx(
            r"\b(pipeline|calendar|schedule).{0,20}\b(dry|empty|slow|thin)\b"
        )),
        ("appointments_needed", _rx(
            r"\b(need|want|looking for).{0,20}\b"
            r"(\d+\s*(?:-|to)\s*\d+\s*)?(qualified )?appointments?\b"
        )),
    ),
    "PAID_MEDIA_FAILURE": (
        ("ads_unprofitable", _rx(
            r"\b(google|meta|facebook|paid|ppc).{0,18}\bads?\b.{0,30}\b"
            r"(not profitable|unprofitable|not working|losing money|waste|wasting)\b"
        )),
        ("high_cpl", _rx(
            r"\b(cost per lead|cpl|lead cost|cost per acquisition|cac)\b"
            r".{0,24}\b(high|too high|expensive|rising)\b"
        )),
        ("poor_lead_quality", _rx(
            r"\b(leads?|appointments?).{0,24}\b"
            r"(bad|poor quality|low quality|junk|unqualified|not qualified)\b"
        )),
        ("agency_failure", _rx(
            r"\b(agency|marketer|marketing company).{0,30}\b"
            r"(not working|failed|wasting|bad leads?|poor results?|no results?)\b"
        )),
    ),
    "CONVERSION_FAILURE": (
        ("missed_calls", _rx(
            r"\b(missed|missing|unanswered).{0,15}\b(calls?|phone calls?)\b"
        )),
        ("slow_followup", _rx(
            r"\b(follow.?up|respond|response).{0,24}\b"
            r"(slow|late|too late|takes too long|not fast enough)\b"
        )),
        ("leads_not_closing", _rx(
            r"\b(leads?|appointments?|estimates?|quotes?).{0,30}\b"
            r"(not closing|won't close|not converting|don't convert|low conversion)\b"
        )),
        ("quote_no_show", _rx(
            r"\b(quote|estimate|appointment).{0,20}\b"
            r"(no.?show|ghosted|ghosting|not showing)\b"
        )),
        ("low_booking_rate", _rx(
            r"\b(booking|booked|appointment).{0,18}\b"
            r"(rate|conversion).{0,18}\b(low|poor|bad)\b"
        )),
    ),
    "GROWTH_TRIGGER": (
        ("new_location", _rx(
            r"\b(opening|opened|launching|expanding to).{0,25}\b"
            r"(new )?(location|office|branch|market)\b"
        )),
        ("new_service", _rx(
            r"\b(launching|launched|adding|added|offering).{0,24}\b"
            r"(new )?(service|product|line)\b"
        )),
        ("hiring_sales", _rx(
            r"\b(hiring|hire).{0,18}\b(sales|setter|closer|appointment setter)\b"
        )),
        ("hiring_marketing", _rx(
            r"\b(hiring|hire).{0,18}\b(marketing|ppc|seo|growth)\b"
        )),
        ("geographic_expansion", _rx(
            r"\b(expanding|expansion|entering|moving into).{0,24}\b"
            r"(new )?(city|cities|state|states|market|markets|territory|territories)\b"
        )),
    ),
    "BUYER_DEMAND": (
        ("buying_calls", _rx(
            r"\b(buying|buy|need|looking for).{0,20}\b"
            r"(inbound )?(calls?|pay per call|ppc calls?)\b"
        )),
        ("buying_leads", _rx(
            r"\b(buying|buy|need|looking for).{0,20}\b"
            r"(leads?|data leads?|cpl leads?)\b"
        )),
        ("need_publishers", _rx(
            r"\b(need|looking for|seeking).{0,20}\b"
            r"(publishers?|affiliates?|traffic partners?)\b"
        )),
        ("need_more_volume", _rx(
            r"\b(need|want|can take|looking for).{0,24}\b"
            r"(more )?(volume|traffic|calls?|leads?)\b"
        )),
        ("capacity_available", _rx(
            r"\b(capacity|cap).{0,20}\b(open|available|increased|more)\b"
        )),
    ),
    "VENDOR_SEARCH": (
        ("looking_for_agency", _rx(
            r"\b(looking for|need|recommend).{0,25}\b"
            r"(marketing|lead gen|lead generation|growth).{0,18}\bagency\b"
        )),
        ("looking_for_ppc_help", _rx(
            r"\b(looking for|need|recommend).{0,25}\b"
            r"(ppc|google ads|paid ads|meta ads).{0,20}\b"
            r"(help|expert|consultant|agency|specialist)\b"
        )),
        ("recommend_lead_gen", _rx(
            r"\b(recommend|recommendation|anyone use|who do you use).{0,30}\b"
            r"(lead gen|lead generation|lead company|lead service)\b"
        )),
        ("need_marketing_help", _rx(
            r"\b(need|looking for|want).{0,25}\b"
            r"(marketing|growth|customer acquisition).{0,20}\b"
            r"(help|expert|consultant|specialist)\b"
        )),
    ),
}

DIRECT_NEED = _rx(
    r"\b(need|looking for|want|seeking|recommend|help|struggling|not working)\b"
)
URGENCY = _rx(
    r"\b(asap|urgent|urgently|right now|immediately|this week|this month|"
    r"need.{0,12}(more|help)|trying to fix)\b"
)
SPEND_EVIDENCE = _rx(
    r"(\bspent?\b.{0,20}(?:\$|£|€|\d)|"
    r"\bbudget\b.{0,20}(?:\$|£|€|\d)|"
    r"\b(?:running|paying for|using)\b.{0,18}\b"
    r"(google ads|meta ads|facebook ads|ppc|agency|lead service|lead vendor)\b|"
    r"\b(?:hire|hiring|pay)\b.{0,18}\b"
    r"(agency|expert|consultant|specialist|marketer)\b)"
)

SOURCE_RELIABILITY = {
    "reddit_atom": 0.90,
    "reddit_public_search": 0.68,
    "linkedin_public_search": 0.62,
    "public_web_search": 0.60,
}


@dataclass(frozen=True)
class IntentDimensions:
    intent_confidence: float | None = None
    identity_confidence: float | None = None
    pain_severity: float | None = None
    commercial_urgency: float | None = None
    ability_to_pay: float | None = None
    source_reliability: float | None = None
    recency: float | None = None
    offer_fit: float | None = None
    outreach_readiness: float | None = None
    estimated_opportunity_value: float | None = None

    def as_dict(self) -> dict[str, float | None]:
        return asdict(self)


@dataclass(frozen=True)
class IntentAssessment:
    intent_types: tuple[str, ...]
    dimensions: IntentDimensions
    signal_priority_score: int | None
    source_evidence_class: str = "OBSERVED"
    classification_evidence_class: str = "INFERRED"
    canonical_buyer_intent: bool = False
    willingness_to_pay_inferred: bool = False
    revenue_inferred: bool = False
    identity_state: str = "unresolved"
    outreach_authority: str = "none"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _bounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(float(value), 1.0)), 4)


def classify_intent_types(text: str) -> tuple[str, ...]:
    value = _clean(text)
    matches: list[str] = []
    for family, rules in INTENT_TAXONOMY.items():
        for subtype, pattern in rules:
            if pattern.search(value):
                matches.append(f"{family}.{subtype}")
    return tuple(dict.fromkeys(matches))


def _parse_time(value: Any) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def recency_score(
    observed_at: str,
    *,
    now: datetime | None = None,
) -> float | None:
    observed = _parse_time(observed_at)
    if observed is None:
        return None
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = max(0.0, (current - observed).total_seconds() / 3600.0)
    if age_hours <= 6:
        return 1.0
    if age_hours <= 24:
        return 0.9
    if age_hours <= 72:
        return 0.75
    if age_hours <= 168:
        return 0.55
    if age_hours <= 720:
        return 0.35
    return 0.2


def _pain_severity(intent_types: tuple[str, ...]) -> float | None:
    if not intent_types:
        return None
    severe = {
        "DEMAND_SHORTAGE.pipeline_dry",
        "DEMAND_SHORTAGE.need_more_leads",
        "PAID_MEDIA_FAILURE.ads_unprofitable",
        "PAID_MEDIA_FAILURE.poor_lead_quality",
        "CONVERSION_FAILURE.leads_not_closing",
    }
    moderate = {
        "DEMAND_SHORTAGE.appointments_needed",
        "DEMAND_SHORTAGE.not_enough_jobs",
        "PAID_MEDIA_FAILURE.high_cpl",
        "PAID_MEDIA_FAILURE.agency_failure",
        "CONVERSION_FAILURE.missed_calls",
        "CONVERSION_FAILURE.slow_followup",
        "CONVERSION_FAILURE.quote_no_show",
        "CONVERSION_FAILURE.low_booking_rate",
    }
    if any(item in severe for item in intent_types):
        return 0.85
    if any(item in moderate for item in intent_types):
        return 0.70
    return 0.50


def _commercial_urgency(
    text: str,
    intent_types: tuple[str, ...],
) -> float | None:
    if not intent_types:
        return None
    if URGENCY.search(text):
        return 0.85
    urgent_families = (
        "DEMAND_SHORTAGE.",
        "PAID_MEDIA_FAILURE.",
        "VENDOR_SEARCH.",
    )
    if any(item.startswith(urgent_families) for item in intent_types):
        return 0.65
    return 0.45


def _intent_confidence(
    text: str,
    intent_types: tuple[str, ...],
) -> float | None:
    if not intent_types:
        return None
    score = 0.35 + min(len(intent_types), 4) * 0.12
    if DIRECT_NEED.search(text):
        score += 0.12
    return _bounded(score)


def _ability_to_pay(text: str) -> float | None:
    return 0.70 if SPEND_EVIDENCE.search(text) else None


def _priority(dimensions: IntentDimensions) -> int | None:
    weighted = (
        ("intent_confidence", 0.30),
        ("pain_severity", 0.20),
        ("commercial_urgency", 0.20),
        ("source_reliability", 0.15),
        ("recency", 0.15),
    )
    values = dimensions.as_dict()
    numerator = 0.0
    denominator = 0.0
    for key, weight in weighted:
        value = values[key]
        if value is None:
            continue
        numerator += value * weight
        denominator += weight
    if denominator <= 0:
        return None
    return int(round(100.0 * numerator / denominator))


def assess_intent_v2(
    text: str,
    *,
    source_mode: str,
    observed_at: str = "",
    now: datetime | None = None,
) -> IntentAssessment:
    value = _clean(text)
    intent_types = classify_intent_types(value)
    dimensions = IntentDimensions(
        intent_confidence=_intent_confidence(value, intent_types),
        identity_confidence=None,
        pain_severity=_pain_severity(intent_types),
        commercial_urgency=_commercial_urgency(value, intent_types),
        ability_to_pay=_ability_to_pay(value),
        source_reliability=SOURCE_RELIABILITY.get(source_mode),
        recency=recency_score(observed_at, now=now),
        offer_fit=None,
        outreach_readiness=None,
        estimated_opportunity_value=None,
    )
    return IntentAssessment(
        intent_types=intent_types,
        dimensions=dimensions,
        signal_priority_score=_priority(dimensions),
    )
