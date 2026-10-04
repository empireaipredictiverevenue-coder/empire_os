"""Typed deterministic classification for EmpireOS community intent.

This module classifies public community evidence into inspectable intent
dimensions. It does not resolve identity, create canonical prospects, infer
verified buyer intent, recognize revenue, or grant outbound authority.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


OBSERVED = "OBSERVED"
INFERRED = "INFERRED"


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


INTENT_ONTOLOGY: dict[str, dict[str, tuple[re.Pattern[str], ...]]] = {
    "DEMAND_SHORTAGE": {
        "need_more_leads": (
            _rx(r"\bneed(?:ing)?\s+(?:more\s+)?(?:qualified\s+)?leads?\b"),
            _rx(r"\bneed(?:ing)?\s+(?:more\s+)?appointments?\b"),
            _rx(r"\bneed(?:ing)?\s+(?:more\s+)?customers?\b"),
        ),
        "not_enough_jobs": (
            _rx(r"\bnot\s+enough\s+(?:work|jobs?|customers?|leads?)\b"),
            _rx(r"\bneed\s+(?:more\s+)?jobs?\b"),
        ),
        "pipeline_dry": (
            _rx(r"\bpipeline\s+(?:is\s+)?(?:dry|empty|slow|weak)\b"),
            _rx(r"\b(?:dry|empty)\s+pipeline\b"),
        ),
        "appointments_needed": (
            _rx(r"\b(?:need|want|looking\s+for)\s+\d+\s*(?:-|to)?\s*\d*\s*(?:more\s+)?(?:qualified\s+)?appointments?\b"),
            _rx(r"\bmore\s+(?:qualified\s+)?appointments?\s+(?:per|a)\s+(?:week|month)\b"),
        ),
    },
    "PAID_MEDIA_FAILURE": {
        "ads_unprofitable": (
            _rx(r"\b(?:google|facebook|meta|paid)?\s*ads?.{0,30}\b(?:not|aren't|isn't|never)\s+(?:profitable|working|converting)\b"),
            _rx(r"\b(?:not|never)\s+(?:made|making).{0,20}\bads?\s+profitable\b"),
            _rx(r"\bwast(?:e|ed|ing).{0,24}\b(?:ad\s+spend|ppc|google\s+ads?|facebook\s+ads?)\b"),
        ),
        "high_cpl": (
            _rx(r"\b(?:cpl|cost\s+per\s+lead).{0,16}\b(?:high|expensive|too\s+high)\b"),
            _rx(r"\bleads?.{0,16}\btoo\s+expensive\b"),
        ),
        "poor_lead_quality": (
            _rx(r"\b(?:bad|poor|low)[ -]?quality\s+leads?\b"),
            _rx(r"\blead\s+quality.{0,16}\b(?:bad|poor|terrible|low)\b"),
            _rx(r"\b(?:junk|fake|unqualified)\s+leads?\b"),
        ),
        "agency_failure": (
            _rx(r"\b(?:agency|marketer).{0,28}\b(?:not\s+working|failed|wasting|poor\s+results|no\s+results)\b"),
            _rx(r"\b(?:fire|replace|switch)\s+(?:our\s+)?(?:agency|marketing\s+agency)\b"),
        ),
    },
    "CONVERSION_FAILURE": {
        "missed_calls": (
            _rx(r"\bmiss(?:ed|ing)\s+(?:customer\s+)?calls?\b"),
            _rx(r"\bcalls?.{0,18}\b(?:go|going)\s+unanswered\b"),
        ),
        "slow_followup": (
            _rx(r"\b(?:slow|late|delayed)\s+follow[ -]?up\b"),
            _rx(r"\bnot\s+following\s+up\b"),
            _rx(r"\bfollow[ -]?up.{0,20}\b(?:too\s+slow|takes\s+too\s+long)\b"),
        ),
        "leads_not_closing": (
            _rx(r"\bleads?.{0,24}\b(?:not|aren't|isn't)\s+(?:closing|converting)\b"),
            _rx(r"\bcan't\s+(?:close|convert).{0,20}\bleads?\b"),
            _rx(r"\blow\s+(?:close|conversion)\s+rate\b"),
        ),
        "quote_no_show": (
            _rx(r"\b(?:quote|estimate)\s+(?:no[ -]?show|ghost(?:ed|ing)?)\b"),
            _rx(r"\bno[ -]?shows?.{0,18}\b(?:quote|estimate|appointment)\b"),
        ),
        "low_booking_rate": (
            _rx(r"\blow\s+booking\s+rate\b"),
            _rx(r"\bleads?.{0,20}\bnot\s+booking\b"),
        ),
    },
    "GROWTH_TRIGGER": {
        "new_location": (
            _rx(r"\bopening\s+(?:a\s+)?new\s+(?:location|office|branch)\b"),
            _rx(r"\bnew\s+(?:location|branch)\b"),
        ),
        "new_service": (
            _rx(r"\blaunch(?:ing|ed)?\s+(?:a\s+)?new\s+service\b"),
            _rx(r"\badding\s+(?:a\s+)?new\s+service\b"),
        ),
        "hiring_sales": (
            _rx(r"\bhiring.{0,20}\b(?:sales|setter|closer|business\s+development)\b"),
        ),
        "hiring_marketing": (
            _rx(r"\bhiring.{0,20}\b(?:marketing|growth|ppc|seo)\b"),
        ),
        "geographic_expansion": (
            _rx(r"\bexpanding\s+(?:into|to|across)\b"),
            _rx(r"\bnew\s+(?:market|territory|service\s+area)\b"),
        ),
    },
    "BUYER_DEMAND": {
        "buying_calls": (
            _rx(r"\b(?:buy|buying|purchase|purchasing)\s+(?:qualified\s+)?calls?\b"),
            _rx(r"\bneed\s+(?:more\s+)?(?:inbound\s+)?calls?\b"),
        ),
        "buying_leads": (
            _rx(r"\b(?:buy|buying|purchase|purchasing)\s+(?:qualified\s+)?leads?\b"),
            _rx(r"\blooking\s+for\s+(?:a\s+)?lead\s+(?:vendor|provider|supplier)\b"),
        ),
        "need_publishers": (
            _rx(r"\bneed\s+(?:more\s+)?publishers?\b"),
            _rx(r"\blooking\s+for\s+publishers?\b"),
        ),
        "need_more_volume": (
            _rx(r"\bneed\s+(?:more\s+)?volume\b"),
            _rx(r"\bcan\s+take\s+(?:more|additional)\s+(?:volume|leads?|calls?)\b"),
        ),
        "capacity_available": (
            _rx(r"\bcapacity\s+(?:available|open)\b"),
            _rx(r"\broom\s+for\s+(?:more|additional)\s+(?:leads?|calls?|jobs?)\b"),
        ),
    },
    "VENDOR_SEARCH": {
        "looking_for_agency": (
            _rx(r"\blooking\s+for\s+(?:a\s+)?(?:marketing|lead\s+gen|advertising)\s+agency\b"),
            _rx(r"\brecommend.{0,24}\b(?:marketing|lead\s+gen|advertising)\s+agency\b"),
        ),
        "looking_for_ppc_help": (
            _rx(r"\blooking\s+for.{0,20}\b(?:ppc|google\s+ads?|paid\s+ads?)\s+(?:help|expert|specialist|agency)\b"),
            _rx(r"\bneed\s+help\s+with\s+(?:ppc|google\s+ads?|paid\s+ads?)\b"),
        ),
        "recommend_lead_gen": (
            _rx(r"\brecommend.{0,24}\b(?:lead\s+gen|lead\s+generation|lead\s+company|lead\s+provider)\b"),
        ),
        "need_marketing_help": (
            _rx(r"\bneed\s+(?:some\s+)?(?:marketing|lead\s+generation)\s+help\b"),
            _rx(r"\blooking\s+for\s+(?:someone|somebody).{0,24}\b(?:marketing|lead\s+generation|ppc|seo)\b"),
        ),
    },
}

DIRECT_INTENT = (
    _rx(r"\bneed\b"),
    _rx(r"\blooking\s+for\b"),
    _rx(r"\brecommend(?:ation|ations)?\b"),
    _rx(r"\bstruggling\b"),
    _rx(r"\bhelp\b"),
)

SPEND_EVIDENCE = (
    _rx(r"\bspen(?:d|ding|t)\s+(?:£|\$|usd|gbp)?\s*\d"),
    _rx(r"\b(?:£|\$)\s*\d[\d,]*(?:\.\d+)?\s*(?:per\s+month|\/month|monthly|on\s+ads?)?\b"),
    _rx(r"\bbudget\s+(?:is|of|around|about)?\s*(?:£|\$|usd|gbp)?\s*\d"),
    _rx(r"\b(?:already|currently)\s+(?:paying|running|using).{0,24}\b(?:ads?|agency|ppc)\b"),
)

URGENCY_EVIDENCE = (
    _rx(r"\b(?:urgent|urgently|asap|right\s+now|immediately)\b"),
    _rx(r"\bthis\s+(?:week|month|quarter)\b"),
    _rx(r"\bper\s+week\b"),
    _rx(r"\bneed.{0,24}\b(?:now|today|this\s+week)\b"),
)

SOURCE_RELIABILITY = {
    "linkedin": 0.80,
    "reddit": 0.75,
    "public_web": 0.65,
}


@dataclass(frozen=True)
class IntentAssessment:
    intent_categories: tuple[str, ...]
    intent_signals: tuple[str, ...]
    intent_confidence: float
    identity_confidence: float | None
    pain_severity: float
    commercial_urgency: float
    ability_to_pay: float | None
    source_reliability: float
    recency: float | None
    offer_fit: float | None
    outreach_readiness: float | None
    estimated_opportunity_value: float | None
    source_evidence_class: str = OBSERVED
    assessment_class: str = INFERRED
    verified_buyer_intent: bool = False
    verified_revenue: bool = False
    outbound_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _bounded(value: float) -> float:
    return round(max(0.0, min(float(value), 1.0)), 4)


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
    observed_at: Any,
    *,
    now: datetime | None = None,
) -> float | None:
    observed = _parse_time(observed_at)
    if observed is None:
        return None
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_days = max(0.0, (current - observed).total_seconds() / 86400.0)
    if age_days <= 1:
        return 1.0
    if age_days <= 3:
        return 0.9
    if age_days <= 7:
        return 0.75
    if age_days <= 30:
        return 0.5
    return 0.25


def _ontology_hits(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    categories: list[str] = []
    signals: list[str] = []
    for category, children in INTENT_ONTOLOGY.items():
        matched_category = False
        for signal, patterns in children.items():
            if any(pattern.search(text) for pattern in patterns):
                signals.append(f"{category}.{signal}")
                matched_category = True
        if matched_category:
            categories.append(category)
    return tuple(categories), tuple(signals)


def assess_intent(
    text: str,
    *,
    source: str,
    observed_at: Any = None,
    now: datetime | None = None,
) -> IntentAssessment:
    value = _clean(text)
    source_key = _clean(source).lower()
    categories, signals = _ontology_hits(value)

    direct_hits = sum(bool(pattern.search(value)) for pattern in DIRECT_INTENT)
    spend_hits = sum(bool(pattern.search(value)) for pattern in SPEND_EVIDENCE)
    urgency_hits = sum(bool(pattern.search(value)) for pattern in URGENCY_EVIDENCE)

    confidence = _bounded(
        0.15
        + min(0.45, 0.12 * len(signals))
        + min(0.20, 0.05 * direct_hits)
        + (0.10 if len(categories) >= 2 else 0.0)
    )

    severity_weights = {
        "DEMAND_SHORTAGE": 0.72,
        "PAID_MEDIA_FAILURE": 0.82,
        "CONVERSION_FAILURE": 0.78,
        "GROWTH_TRIGGER": 0.45,
        "BUYER_DEMAND": 0.70,
        "VENDOR_SEARCH": 0.62,
    }
    pain = max(
        (severity_weights.get(category, 0.0) for category in categories),
        default=0.0,
    )
    if len(categories) >= 2:
        pain = min(1.0, pain + 0.08)

    urgency = _bounded(
        (0.34 if categories else 0.0)
        + min(0.36, urgency_hits * 0.18)
        + (0.14 if "VENDOR_SEARCH" in categories else 0.0)
        + (0.12 if "DEMAND_SHORTAGE" in categories else 0.0)
    )

    ability_to_pay = None
    if spend_hits:
        ability_to_pay = _bounded(0.65 + min(0.25, spend_hits * 0.10))

    offer_fit = None
    if categories:
        if any(
            category in categories
            for category in (
                "DEMAND_SHORTAGE",
                "PAID_MEDIA_FAILURE",
                "CONVERSION_FAILURE",
                "VENDOR_SEARCH",
            )
        ):
            offer_fit = 0.9
        elif "BUYER_DEMAND" in categories:
            offer_fit = 0.72
        elif "GROWTH_TRIGGER" in categories:
            offer_fit = 0.55

    return IntentAssessment(
        intent_categories=categories,
        intent_signals=signals,
        intent_confidence=confidence,
        identity_confidence=None,
        pain_severity=_bounded(pain),
        commercial_urgency=urgency,
        ability_to_pay=ability_to_pay,
        source_reliability=SOURCE_RELIABILITY.get(source_key, 0.5),
        recency=recency_score(observed_at, now=now),
        offer_fit=offer_fit,
        outreach_readiness=None,
        estimated_opportunity_value=None,
    )
