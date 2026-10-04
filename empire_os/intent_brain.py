"""Deterministic commercial-intent world model for EmpireOS.

Intent Brain converts noisy public observations into a typed commercial state.

It does NOT:
- create canonical prospects;
- authorize outreach;
- claim actual revenue;
- infer unknown identity as fact;
- allow model inference to bypass deterministic gates.

Semantic/model providers may later contribute bounded shadow evidence, but this
module owns the deterministic promotion contract.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


SCHEMA_VERSION = "empire.intent_brain.v1"

SOCIAL_HOSTS = {
    "reddit.com",
    "old.reddit.com",
    "linkedin.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "instagram.com",
    "tiktok.com",
}

CAREER_PATTERNS = (
    r"\bcareer advice\b",
    r"\bmy sales career\b",
    r"\bwhich (?:of these )?jobs?\b",
    r"\bjob (?:1|2|3)\b",
    r"\binterview(?:ing)? for\b",
    r"\bland a .* job\b",
    r"\bmoving from .* sales to\b",
    r"\bwhat roles? should i\b",
    r"\bwhere should i take my career\b",
    r"\bcommission job\b",
)

VENDOR_PATTERNS = (
    r"\bwe help (?:companies|businesses|teams|contractors)\b",
    r"\bi help (?:companies|businesses|teams|contractors)\b",
    r"\bour (?:service|platform|solution|agency|clients)\b",
    r"\bbook (?:a )?(?:demo|call)\b",
    r"\bdm me\b",
    r"\bmessage me\b",
    r"\bwe build\b",
    r"\bwe provide\b",
    r"\bwe offer\b",
)

BUYER_PATTERNS = (
    r"\bwe need\b",
    r"\bi need\b",
    r"\bwe are looking for\b",
    r"\bi am looking for\b",
    r"\blooking for (?:a|an|someone|help|software|agency|specialist|provider)\b",
    r"\bneed more (?:leads|customers|appointments|clients|sales)\b",
    r"\bstruggling with\b",
    r"\bnot profitable\b",
    r"\bpoor roi\b",
    r"\bwasting money\b",
    r"\bleads? (?:are|is) not converting\b",
    r"\bmanual follow[- ]?up\b",
    r"\blosing leads\b",
    r"\bneed .* per week\b",
)

OWNER_PATTERNS = (
    r"\bi own\b",
    r"\bowner\b",
    r"\bfounder\b",
    r"\bmy company\b",
    r"\bmy business\b",
    r"\bour company\b",
    r"\bour business\b",
    r"\bwe run\b",
)

DECISION_MAKER_PATTERNS = (
    r"\bceo\b",
    r"\bmanaging director\b",
    r"\bcommercial director\b",
    r"\bsales director\b",
    r"\bhead of sales\b",
    r"\bvp sales\b",
)

URGENCY_HIGH = (
    r"\basap\b",
    r"\bimmediately\b",
    r"\bright now\b",
    r"\bthis week\b",
    r"\bthis month\b",
    r"\bneed .* per week\b",
    r"\bactively looking\b",
)

VENDOR_SEARCH_PATTERNS = (
    r"\blooking for (?:a|an|someone|software|agency|specialist|provider)\b",
    r"\brecommend (?:a|an|someone|software|agency|specialist|provider)\b",
    r"\bwho can help\b",
)

EVALUATION_PATTERNS = (
    r"\bpricing\b",
    r"\bquote\b",
    r"\bproposal\b",
    r"\bdemo\b",
    r"\bcompare\b",
    r"\bversus\b",
    r"\bvs\b",
)

# Explicit commercial procurement. These are materially stronger than generic
# pain-language because the author is actively seeking capability/provider help.
PROCUREMENT_PATTERNS = (
    # Permit a bounded technology/service descriptor before the provider noun:
    # "Looking for a HubSpot CRM + Sales Automation Expert"
    # "Looking for: AI & Automation Specialist"
    r"\blooking for\s*:?\s*(?:a|an)?\s*(?:(?:[\w&+/#.\-]+)\s+){0,8}(?:expert|specialist|consultant|freelancer|agency|provider)\b",
    r"\bseeking\s+(?:a|an)?\s*(?:(?:[\w&+/#.\-]+)\s+){0,8}(?:expert|specialist|consultant|freelancer|agency|provider)\b",
    r"\bneed\s+(?:a|an)?\s*(?:(?:[\w&+/#.\-]+)\s+){0,8}(?:expert|specialist|consultant|freelancer|agency|provider)\b",
    r"\blooking for\s*:?\s*(?:a|an)?\s*(?:software|platform|solution)\b",
    r"\bneed help (?:with|implementing|fixing|automating)\b",
    r"\bwho can help (?:us|me)\b",
    r"\brecommend\s+(?:a|an)?\s*(?:(?:[\w&+/#.\-]+)\s+){0,6}(?:expert|specialist|consultant|agency|provider|software)\b",
)

# Hiring is commercially interesting account evidence, but an employment ad is
# not direct buyer intent for Empire's services. Preserve it as WATCH evidence.
EMPLOYMENT_HIRING_PATTERNS = (
    # Explicit recruitment markers must outrank superficially similar
    # procurement language such as "Sales Partner" or "Acquisition Partner".
    r"\[\s*hiring\s*\]",
    r"\bwe are hiring\b",
    r"\bwe're hiring\b",
    r"\bnow hiring\b",
    r"\bhiring\s+(?:a|an)\b",
    r"\bopen role\b",
    r"\bjob opening\b",
    r"\bjoin our team\b",
    r"\bbuscamos\s+(?:a|un|una)\b",
    r"\bspannende rolle\b",
    r"\bcommission[- ]based model\b",
    r"\bthe role involves\b",
    r"\bfractional cmo\b",
    r"\bhead of marketing\b",
)

THIRD_PARTY_REFERRAL_PATTERNS = (
    r"\bwho can help him\b",
    r"\bwho can help her\b",
    r"\bwho can help them\b",
    r"\blooking for .{0,80}\bfor (?:him|her|them)\b",
)

# Educational/vendor/case-study content often contains the exact pain phrases
# buyers use. It must not be promoted merely because the copy says "losing
# leads", "pipeline", etc.
PROMOTIONAL_CONTENT_PATTERNS = (
    r"\bhow we helped\b",
    r"\bhow (?:i|we) help\b",
    r"\bhere'?s how to fix\b",
    r"\bstop losing leads\b",
    r"\breplace manual follow[- ]?up with\b",
    r"\bwhy do you need lead generation\b",
    r"\bcase study\b",
    r"\bour clients?\b",
    r"\bwe generated\b",
    r"\bwe increased\b",
    # Seller-side invitation language must not masquerade as procurement.
    r"\banyone looking for\b",
    r"\bif (?:you|anyone) (?:are|is) looking for\b",
    r"\bthe businesses winning right now\b",
    r"\bmanual follow[- ]?up\s+smart automation\b",
    r"\bthat'?s the difference between\b",
)

NICHES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "roofing",
        ("home_services", "roofing"),
        ("roof", "roofing", "roofer", "shingle", "storm damage"),
    ),
    (
        "hvac",
        ("home_services", "hvac"),
        ("hvac", "air conditioning", "heating", "home comfort"),
    ),
    (
        "solar",
        ("home_services", "solar"),
        ("solar", "photovoltaic", "pv installer"),
    ),
    (
        "plumbing",
        ("home_services", "plumbing"),
        ("plumbing", "plumber"),
    ),
    (
        "legal",
        ("professional_services", "legal"),
        ("law firm", "lawyer", "attorney", "legal", "mass tort"),
    ),
    (
        "automotive",
        ("automotive",),
        ("dealership", "car sales", "automotive", "auto dealer"),
    ),
    (
        "saas",
        ("technology", "saas"),
        ("saas", "software company", "software business"),
    ),
    (
        "b2b_services",
        ("b2b_services",),
        ("b2b", "agency", "consulting", "professional services"),
    ),
)

PAINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "insufficient_qualified_demand",
        (
            "need more leads",
            "need more customers",
            "need more appointments",
            "qualified appointments",
            "empty pipeline",
            "pipeline is empty",
        ),
    ),
    (
        "unprofitable_paid_acquisition",
        (
            "google ads",
            "search ads",
            "paid ads",
            "not profitable",
            "poor roi",
            "wasting money",
        ),
    ),
    (
        "slow_or_manual_follow_up",
        (
            "manual follow-up",
            "manual follow up",
            "slow follow-up",
            "slow follow up",
            "losing leads",
        ),
    ),
    (
        "conversion_underperformance",
        (
            "not converting",
            "conversion rate",
            "close rate",
            "not closing",
        ),
    ),
    (
        "identity_or_contact_gap",
        (
            "decision-maker",
            "decision maker",
            "contact data",
            "enrichment",
        ),
    ),
    (
        "automation_gap",
        (
            "automation",
            "manual process",
            "manual busywork",
            "crm workflow",
        ),
    ),
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _combined(observation: Mapping[str, Any]) -> str:
    values = (
        observation.get("title"),
        observation.get("text"),
        observation.get("details"),
        observation.get("summary"),
    )
    return " ".join(_text(v) for v in values if _text(v)).casefold()


def _matches(patterns: Sequence[str], text: str) -> int:
    return sum(bool(re.search(pattern, text, flags=re.I)) for pattern in patterns)


def _host(value: Any) -> str:
    try:
        host = urlparse(_text(value)).netloc.casefold()
    except ValueError:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _is_social_url(value: Any) -> bool:
    host = _host(value)
    return bool(host and any(
        host == social or host.endswith("." + social)
        for social in SOCIAL_HOSTS
    ))


def _evidence_urls(observation: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for source in (
        observation.get("evidence_urls"),
        observation.get("external_evidence_urls"),
    ):
        if isinstance(source, (list, tuple)):
            values.extend(_text(value) for value in source if _text(value))

    url = _text(observation.get("url"))
    if url:
        values.append(url)

    return list(dict.fromkeys(values))


def _first_party_candidates(observation: Mapping[str, Any]) -> list[str]:
    output = []
    for url in _evidence_urls(observation):
        host = _host(url)
        if (
            url.startswith(("http://", "https://"))
            and host
            and not _is_social_url(url)
        ):
            output.append(url)
    return output


def _parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def temporal_decay(
    observed_at: Any,
    *,
    now: datetime | None = None,
    half_life_days: float = 30.0,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed = _parse_time(observed_at)

    if observed is None:
        return {
            "age_days": None,
            "decay_factor": 1.0,
            "freshness": "unknown",
        }

    age_days = max(0.0, (current - observed).total_seconds() / 86400.0)
    decay = math.exp(-math.log(2.0) * age_days / half_life_days)

    if age_days <= 7:
        freshness = "fresh"
    elif age_days <= 30:
        freshness = "recent"
    elif age_days <= 90:
        freshness = "aging"
    else:
        freshness = "stale"

    return {
        "age_days": round(age_days, 2),
        "decay_factor": round(decay, 4),
        "freshness": freshness,
    }


def classify_actor(text: str) -> tuple[str, float, list[str]]:
    career = _matches(CAREER_PATTERNS, text)
    vendor = _matches(VENDOR_PATTERNS, text)
    owner = _matches(OWNER_PATTERNS, text)
    decision_maker = _matches(DECISION_MAKER_PATTERNS, text)

    reasons: list[str] = []

    if career:
        reasons.append("career_or_job_seeking_language")
        return "job_seeker", min(0.99, 0.82 + career * 0.04), reasons

    if vendor >= 2:
        reasons.append("vendor_promotional_language")
        return "vendor", min(0.98, 0.76 + vendor * 0.05), reasons

    if owner:
        reasons.append("owner_operator_language")
        return "owner_operator", min(0.98, 0.74 + owner * 0.06), reasons

    if decision_maker:
        reasons.append("decision_maker_role_language")
        return (
            "decision_maker",
            min(0.96, 0.72 + decision_maker * 0.06),
            reasons,
        )

    reasons.append("actor_not_explicit")
    return "unknown", 0.35, reasons


def classify_niche(
    observation: Mapping[str, Any],
    text: str,
) -> tuple[str, list[str], float]:
    supplied = _text(observation.get("niche")).casefold()

    for niche, path, terms in NICHES:
        hits = sum(term in text for term in terms)
        supplied_hit = supplied in {niche, path[-1]} and supplied not in {
            "",
            "b2b",
            "commercial_intent",
        }
        if hits or supplied_hit:
            confidence = min(
                0.95,
                0.58 + hits * 0.10 + (0.12 if supplied_hit else 0.0),
            )
            return niche, list(path), confidence

    if supplied and supplied not in {"b2b", "commercial_intent"}:
        return supplied.replace(" ", "_"), [supplied.replace(" ", "_")], 0.55

    return "unknown", [], 0.25


def classify_pains(text: str) -> list[str]:
    output: list[str] = []
    for pain, terms in PAINS:
        if any(term in text for term in terms):
            output.append(pain)
    return output


def classify_urgency(text: str, pain_points: Sequence[str]) -> tuple[str, float]:
    high_hits = _matches(URGENCY_HIGH, text)
    if high_hits:
        return "high", min(0.95, 0.72 + high_hits * 0.06)
    if pain_points:
        return "medium", 0.66
    return "low", 0.45


def classify_orientation(
    text: str,
) -> tuple[str, float, list[str]]:
    """Classify whether a signal is buyer procurement, hiring or seller content."""
    procurement_hits = _matches(PROCUREMENT_PATTERNS, text)
    hiring_hits = _matches(EMPLOYMENT_HIRING_PATTERNS, text)
    referral_hits = _matches(THIRD_PARTY_REFERRAL_PATTERNS, text)
    promotional_hits = _matches(PROMOTIONAL_CONTENT_PATTERNS, text)

    reasons: list[str] = []

    if hiring_hits:
        reasons.append("employment_hiring_language")
        return (
            "employment_hiring",
            min(0.98, 0.82 + hiring_hits * 0.04),
            reasons,
        )

    if referral_hits:
        reasons.append("third_party_referral_language")
        return (
            "third_party_referral",
            min(0.96, 0.80 + referral_hits * 0.05),
            reasons,
        )

    # Explicit seller/case-study language wins over superficially similar
    # procurement phrases such as "Anyone looking for expert ...".
    if promotional_hits:
        reasons.append("educational_or_promotional_content")
        return (
            "seller_content",
            min(0.96, 0.76 + promotional_hits * 0.05),
            reasons,
        )

    if procurement_hits:
        reasons.append("explicit_provider_procurement_language")
        return (
            "buyer_procurement",
            min(0.98, 0.80 + procurement_hits * 0.05),
            reasons,
        )

    return "neutral", 0.40, ["orientation_not_explicit"]


def classify_buying_stage(
    text: str,
    pain_points: Sequence[str],
) -> tuple[str, float]:
    if _matches(EVALUATION_PATTERNS, text):
        return "evaluation", 0.82
    if _matches(VENDOR_SEARCH_PATTERNS, text):
        return "vendor_search", 0.84
    if any(
        pain in {
            "automation_gap",
            "identity_or_contact_gap",
        }
        for pain in pain_points
    ):
        return "solution_aware", 0.68
    if pain_points:
        return "problem_aware", 0.72
    return "unknown", 0.30


def _economic_fit(
    actor_type: str,
    pain_points: Sequence[str],
    urgency: str,
    niche: str,
) -> tuple[str, int]:
    score = 0

    if actor_type in {"owner_operator", "decision_maker"}:
        score += 30
    if pain_points:
        score += min(30, len(pain_points) * 12)
    if urgency == "high":
        score += 20
    elif urgency == "medium":
        score += 10
    if niche != "unknown":
        score += 15

    score = min(100, score)

    if score >= 75:
        return "high", score
    if score >= 45:
        return "medium", score
    return "low", score


def assess_intent(
    observation: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return deterministic commercial intent state for one observation."""
    text = _combined(observation)

    actor_type, actor_confidence, actor_reasons = classify_actor(text)
    orientation, orientation_confidence, orientation_reasons = (
        classify_orientation(text)
    )
    niche, niche_path, niche_confidence = classify_niche(observation, text)
    pain_points = classify_pains(text)
    urgency, urgency_confidence = classify_urgency(text, pain_points)
    buying_stage, buying_stage_confidence = classify_buying_stage(
        text,
        pain_points,
    )

    career_hits = _matches(CAREER_PATTERNS, text)
    vendor_hits = _matches(VENDOR_PATTERNS, text)
    buyer_hits = _matches(BUYER_PATTERNS, text)
    procurement_hits = _matches(PROCUREMENT_PATTERNS, text)
    hiring_hits = _matches(EMPLOYMENT_HIRING_PATTERNS, text)
    referral_hits = _matches(THIRD_PARTY_REFERRAL_PATTERNS, text)
    promotional_hits = _matches(PROMOTIONAL_CONTENT_PATTERNS, text)

    negative_intent_classes: list[str] = []
    contradictions: list[str] = []

    if career_hits:
        negative_intent_classes.append("career_or_job_seeking")

    if actor_type == "vendor":
        negative_intent_classes.append("vendor_or_promotional_content")

    if orientation == "seller_content":
        negative_intent_classes.append("seller_or_educational_content")

    if vendor_hits and buyer_hits:
        contradictions.append("buyer_and_vendor_language_both_present")

    if actor_type == "unknown" and buyer_hits:
        contradictions.append("buyer_pain_without_actor_authority")

    first_party_candidates = _first_party_candidates(observation)
    first_party_verified = (
        observation.get("first_party_verified") is True
        or observation.get("canonical_identity_verified") is True
    )
    social_count = sum(
        1 for url in _evidence_urls(observation) if _is_social_url(url)
    )

    evidence_confidence = 0.30
    if first_party_candidates:
        evidence_confidence += 0.25
    if first_party_verified:
        evidence_confidence += 0.35
    if social_count:
        evidence_confidence += 0.05
    evidence_confidence = min(0.98, evidence_confidence)

    if first_party_verified:
        identity_state = "company_verified"
        identity_confidence = 0.94
    elif first_party_candidates:
        identity_state = "first_party_candidate"
        identity_confidence = 0.62
    elif actor_type in {"owner_operator", "decision_maker"}:
        identity_state = "actor_claim_unresolved"
        identity_confidence = 0.42
    else:
        identity_state = "unresolved"
        identity_confidence = 0.20

    temporal = temporal_decay(
        observation.get("observed_at"),
        now=now,
    )

    intent_confidence = 0.30
    intent_confidence += min(0.28, buyer_hits * 0.08)
    intent_confidence += min(0.18, len(pain_points) * 0.06)

    if orientation == "buyer_procurement":
        intent_confidence += min(0.30, 0.20 + procurement_hits * 0.04)

    if orientation == "employment_hiring":
        intent_confidence -= min(0.18, 0.10 + hiring_hits * 0.04)

    if orientation == "third_party_referral":
        intent_confidence -= min(0.18, 0.10 + referral_hits * 0.04)

    if orientation == "seller_content":
        intent_confidence -= min(
            0.24,
            0.14 + promotional_hits * 0.04,
        )
    if actor_type in {"owner_operator", "decision_maker"}:
        intent_confidence += 0.14
    if urgency == "high":
        intent_confidence += 0.08
    if negative_intent_classes:
        intent_confidence -= 0.18
    if contradictions:
        intent_confidence -= 0.08

    intent_confidence *= float(temporal["decay_factor"])
    intent_confidence = max(0.0, min(0.99, intent_confidence))

    commercial_intent = bool(
        buyer_hits
        and pain_points
        and actor_type not in {"job_seeker", "vendor"}
        and orientation not in {"employment_hiring", "seller_content"}
    )

    if not buyer_hits and pain_points and actor_type in {
        "owner_operator",
        "decision_maker",
    }:
        commercial_intent = True

    # Explicit procurement is commercially meaningful even when the social post
    # does not expose the author's authority yet. It may proceed only to
    # identity resolution, never directly to Buyer Scout.
    if (
        orientation == "buyer_procurement"
        and actor_type not in {"job_seeker", "vendor"}
    ):
        commercial_intent = True

    if orientation in {
        "employment_hiring",
        "third_party_referral",
        "seller_content",
    }:
        commercial_intent = False

    intent_class = "unknown"
    if "insufficient_qualified_demand" in pain_points:
        intent_class = "lead_generation"
    elif "unprofitable_paid_acquisition" in pain_points:
        intent_class = "paid_acquisition_efficiency"
    elif "slow_or_manual_follow_up" in pain_points:
        intent_class = "sales_follow_up_automation"
    elif "conversion_underperformance" in pain_points:
        intent_class = "sales_conversion"
    elif "identity_or_contact_gap" in pain_points:
        intent_class = "contact_intelligence"
    elif "automation_gap" in pain_points:
        intent_class = "workflow_automation"
    elif orientation == "buyer_procurement":
        intent_class = "service_or_software_procurement"
    elif orientation == "employment_hiring":
        intent_class = "hiring_signal"
    elif orientation == "third_party_referral":
        intent_class = "third_party_referral"

    economic_band, economic_score = _economic_fit(
        actor_type,
        pain_points,
        urgency,
        niche,
    )

    repeated_signal_count = int(
        observation.get("repeated_signal_count")
        or observation.get("account_signal_count")
        or 1
    )

    prior_score = observation.get("prior_intent_score")
    current_score = round(intent_confidence * 100)

    if repeated_signal_count >= 3:
        intent_state = "strengthening"
    elif isinstance(prior_score, (int, float)) and current_score < prior_score - 10:
        intent_state = "weakening"
    else:
        intent_state = "observed"

    reason_codes = list(actor_reasons)
    reason_codes.extend(orientation_reasons)

    if negative_intent_classes:
        decision = "REJECT"
        reason_codes.extend(negative_intent_classes)
    elif orientation == "employment_hiring":
        decision = "WATCH"
        reason_codes.append("hiring_signal_not_direct_buyer_intent")
    elif orientation == "third_party_referral":
        decision = "WATCH"
        reason_codes.append("third_party_referral_requires_direct_buyer_evidence")
    elif not commercial_intent:
        decision = "WATCH"
        reason_codes.append("commercial_buyer_intent_not_proven")
    elif (
        orientation == "buyer_procurement"
        and orientation_confidence >= 0.80
        and not first_party_verified
    ):
        decision = "RESOLVE_IDENTITY"
        reason_codes.append(
            "explicit_procurement_requires_first_party_identity"
        )
    elif intent_confidence < 0.50:
        decision = "WATCH"
        reason_codes.append("intent_confidence_below_resolution_threshold")
    elif len(contradictions) >= 2:
        decision = "NEEDS_REVIEW"
        reason_codes.append("multiple_material_contradictions")
    elif not first_party_candidates and not first_party_verified:
        decision = "RESOLVE_IDENTITY"
        reason_codes.append("commercial_intent_requires_identity_resolution")
    elif not first_party_verified:
        decision = "RESOLVE_IDENTITY"
        reason_codes.append("first_party_candidate_requires_verification")
    elif actor_type == "unknown":
        decision = "NEEDS_REVIEW"
        reason_codes.append("actor_authority_unresolved")
    elif intent_confidence < 0.62:
        decision = "NEEDS_REVIEW"
        reason_codes.append("commercial_confidence_requires_review")
    else:
        decision = "BUYER_SCOUT_SEED"
        reason_codes.append("commercial_intent_and_identity_verified")

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "actor_type": actor_type,
        "signal_orientation": orientation,
        "commercial_intent": commercial_intent,
        "intent_class": intent_class,
        "niche": niche,
        "niche_path": niche_path,
        "pain_points": pain_points,
        "urgency": urgency,
        "buying_stage": buying_stage,
        "negative_intent_classes": negative_intent_classes,
        "contradictions": contradictions,
        "identity_state": identity_state,
        "first_party_candidates": first_party_candidates,
        "first_party_verified": first_party_verified,
        "intent_state": intent_state,
        "economic_fit": {
            "band": economic_band,
            "score": economic_score,
            "actual_revenue": False,
        },
        "confidence": {
            "actor": round(actor_confidence, 4),
            "orientation": round(orientation_confidence, 4),
            "niche": round(niche_confidence, 4),
            "intent": round(intent_confidence, 4),
            "identity": round(identity_confidence, 4),
            "urgency": round(urgency_confidence, 4),
            "buying_stage": round(buying_stage_confidence, 4),
            "evidence": round(evidence_confidence, 4),
        },
        "evidence": {
            "evidence_urls": _evidence_urls(observation),
            "first_party_candidate_count": len(first_party_candidates),
            "social_evidence_count": social_count,
        },
        "temporal": temporal,
        "decision": decision,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "outreach_authorized": False,
        "database_write_performed": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
