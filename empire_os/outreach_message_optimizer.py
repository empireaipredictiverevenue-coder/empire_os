"""Deterministic outreach message optimisation for Empire AI.

This module improves first-touch B2B email copy without inventing prospect pain,
proof, pricing, urgency, relationships or revenue. It is analysis/drafting only.
"""
from __future__ import annotations

from email.utils import parseaddr
import re
from typing import Any, Mapping


CONSUMER_MAIL_DOMAINS = frozenset({
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "me.com",
})

C_SUITE_TOKENS = (
    "chief ",
    "ceo",
    "cfo",
    "coo",
    "cro",
    "cmo",
    "cto",
    "cio",
    "president",
    "founder",
    "owner",
    "managing director",
)

_VENDORISH_PHRASES = (
    "predictive revenue intelligence os",
    "best-in-class",
    "leading provider",
    "synergy",
    "leverage",
    "revolutionary",
    "game-changing",
    "cutting-edge",
    "state-of-the-art",
    "world-class",
    "ai-powered",
    "unlock",
    "supercharge",
    "elevate your",
    "transform your",
    "seamless",
    "tailored solution",
    "innovative solution",
    "in today's fast-paced",
    "ever-evolving landscape",
    "delve into",
    "i hope this email finds you well",
    "i wanted to reach out",
    "my name is ",
)

_AI_SLOP_PATTERNS = (
    r"\b(?:unlock|supercharge|revolutioni[sz]e|elevate|transform)\b",
    r"\b(?:cutting[- ]edge|state[- ]of[- ]the[- ]art|world[- ]class)\b",
    r"\b(?:seamless(?:ly)?|robust|holistic|bespoke)\b",
    r"\b(?:powerful|innovative|game[- ]changing) (?:solution|platform|tool)\b",
    r"\b(?:navigate|thrive in) (?:today'?s )?(?:fast[- ]paced|ever[- ]changing) landscape\b",
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _email(value: Any) -> str:
    return parseaddr(str(value or ""))[1].strip().lower()


def _domain(value: Any) -> str:
    email = _email(value)
    return email.rsplit("@", 1)[1] if "@" in email else ""


def _company_token(value: Any) -> str:
    words = [
        part for part in re.split(r"[^A-Za-z0-9]+", _text(value))
        if part
    ]
    if not words:
        return "company"
    generic = {
        "the", "group", "holdings", "services", "partners",
        "company", "companies", "inc", "llc", "ltd", "limited",
    }
    for word in words:
        if word.lower() not in generic:
            return word
    return words[0]


def _topic(reason_now: Any) -> str:
    text = _text(reason_now).lower()
    for needle, label in (
        ("capacity", "capacity"),
        ("demand", "demand"),
        ("territory", "territory"),
        ("market", "market signals"),
        ("revenue", "revenue signals"),
        ("growth", "growth signals"),
        ("hiring", "growth plans"),
        ("permit", "permit signals"),
        ("storm", "storm demand"),
        ("search", "search demand"),
        ("public profile", "customer signals"),
        ("review", "customer signals"),
    ):
        if needle in text:
            return label
    return "growth signals"


def review_sender_identity(
    sender_email: Any,
    *,
    brand_domain: str | None = None,
    enterprise_target: bool = False,
) -> dict[str, Any]:
    """Review sender credibility/alignment without configuring any provider."""
    sender = _email(sender_email)
    domain = _domain(sender)
    expected = _text(brand_domain).lower().lstrip("@")
    blockers: list[str] = []
    warnings: list[str] = []

    if not sender:
        blockers.append("sender_email_missing_or_invalid")
    elif enterprise_target and domain in CONSUMER_MAIL_DOMAINS:
        blockers.append("consumer_mailbox_for_enterprise_target")

    if sender and expected:
        aligned = domain == expected or domain.endswith("." + expected)
        if not aligned:
            blockers.append("sender_not_brand_aligned")
    else:
        aligned = None if not expected else False

    if sender and domain in CONSUMER_MAIL_DOMAINS and not enterprise_target:
        warnings.append("consumer_mailbox_reduces_brand_signal")

    return {
        "sender_email": sender or None,
        "sender_domain": domain or None,
        "brand_domain": expected or None,
        "brand_aligned": aligned,
        "consumer_mailbox": domain in CONSUMER_MAIL_DOMAINS if domain else None,
        "enterprise_target": bool(enterprise_target),
        "blockers": blockers,
        "warnings": warnings,
        "ready_for_enterprise_send_review": not blockers,
        "provider_mutation": False,
        "dns_mutation": False,
        "send_enabled": False,
        "execution_authority": "none",
    }


def _subject_score(value: str) -> tuple[int, list[str]]:
    subject = _text(value)
    issues: list[str] = []
    score = 100
    chars = len(subject)
    words = len(subject.split())

    if chars < 10:
        score -= 10
        issues.append("subject_very_short")
    elif chars > 40:
        score -= 35
        issues.append("subject_too_long")
    elif not 20 <= chars <= 29:
        score -= 8
        issues.append("subject_outside_20_29_character_test_band")

    if not 3 <= words <= 4:
        score -= 10
        issues.append("subject_outside_3_4_word_test_band")
    if re.search(r"[!?]{1,}", subject):
        score -= 8
        issues.append("subject_punctuation_heavy")
    if re.match(r"^(re|fwd):", subject, flags=re.IGNORECASE):
        score -= 40
        issues.append("fake_thread_prefix_forbidden")
    if any(term in subject.lower() for term in (
        "free", "guaranteed", "limited time", "act now",
    )):
        score -= 20
        issues.append("subject_promotional_language")

    return max(score, 0), issues


def build_subject_variants(
    *,
    business_name: str,
    reason_now: str,
    territory: str | None = None,
) -> list[dict[str, Any]]:
    """Build short internal-looking subject tests from observed context."""
    company = _company_token(business_name)
    topic = _topic(reason_now)
    territory_text = _text(territory)

    raw = [
        ("company_only", company),
        ("company_question", f"{company} question"),
        ("one_thing", f"one thing on {company}"),
    ]
    if territory_text:
        raw.append(("territory_company", f"{territory_text} / {company}"))

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for priority, (variant_id, value) in enumerate(raw):
        subject = _text(value)
        key = subject.casefold()
        if not subject or key in seen:
            continue
        seen.add(key)
        score, issues = _subject_score(subject)
        rows.append({
            "variant_id": variant_id,
            "subject": subject,
            "score": score,
            "issues": issues,
            "character_count": len(subject),
            "word_count": len(subject.split()),
            "priority": priority,
        })

    rows.sort(
        key=lambda row: (
            -int(row["score"]),
            int(row["priority"]),
            abs(int(row["character_count"]) - 24),
            int(row["character_count"]),
        )
    )
    return rows


def human_copy_gate(
    *,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Hard reject generic/AI-ish copy before it can enter an experiment."""
    combined = f"{_text(subject)} {_text(body)}".lower()
    blockers: list[str] = []

    if any(re.search(pattern, combined, flags=re.IGNORECASE) for pattern in _AI_SLOP_PATTERNS):
        blockers.append("ai_slop_pattern")
    if any(phrase in combined for phrase in _VENDORISH_PHRASES):
        blockers.append("vendor_or_ai_sounding_language")
    if len(re.findall(r"\b(?:we|our|us)\b", combined)) >= 6:
        blockers.append("brand_monologue")
    if combined.count("!") > 0:
        blockers.append("salesy_exclamation")
    if re.search(r"\b(?:guarantee|guaranteed|guaranteeing)\b", combined):
        blockers.append("unsupported_guarantee")
    if re.search(r"\b(?:10x|100x|massive roi|skyrocket)\b", combined):
        blockers.append("hype_claim")

    return {
        "eligible": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "policy": "human_plain_specific_v1",
        "execution_authority": "none",
    }


def review_message(
    *,
    subject: str,
    body: str,
    cta: str,
    contact_title: str | None = None,
) -> dict[str, Any]:
    """Score drafting quality against Empire's first-touch review policy."""
    issues: list[str] = []
    score = 100
    clean_body = _text(body)
    words = len(clean_body.split())
    lower = clean_body.lower()
    title = _text(contact_title).lower()
    c_suite = any(token in title for token in C_SUITE_TOKENS)

    subject_score, subject_issues = _subject_score(subject)
    if subject_score < 80:
        issues.extend(subject_issues)
        score -= min(30, 100 - subject_score)

    word_limit = 75 if c_suite else 110
    if words > word_limit:
        score -= 25
        issues.append("body_too_long_for_audience")
    if words < 25:
        score -= 5
        issues.append("body_may_be_too_thin")

    vendorish = [
        phrase for phrase in _VENDORISH_PHRASES
        if phrase in lower
    ]
    if vendorish:
        score -= min(30, 10 * len(vendorish))
        issues.append("vendor_or_ai_sounding_language")

    question_count = clean_body.count("?")
    if question_count > 1:
        score -= 10
        issues.append("multiple_questions")
    if not _text(cta):
        score -= 20
        issues.append("cta_missing")

    first_person = len(re.findall(r"\b(?:i|we|our|us)\b", lower))
    prospect_person = len(re.findall(r"\b(?:you|your)\b", lower))
    if first_person > prospect_person + 3:
        score -= 10
        issues.append("sender_centric_copy")

    human_gate = human_copy_gate(subject=subject, body=body)
    if not human_gate["eligible"]:
        score = 0
        issues.extend(human_gate["blockers"])

    return {
        "score": max(score, 0),
        "issues": list(dict.fromkeys(issues)),
        "word_count": words,
        "c_suite": c_suite,
        "human_copy_gate": human_gate,
        "experiment_eligible": bool(human_gate["eligible"] and score >= 80),
        "policy": {
            "c_suite_word_limit": 75,
            "other_word_limit": 110,
            "subject_test_band_characters": "20-29",
            "subject_test_band_words": "3-4",
            "one_primary_ask": True,
            "first_touch_fake_re_fwd": False,
        },
        "drafting_only": True,
        "send_enabled": False,
        "execution_authority": "none",
    }




def build_body_variants(
    *,
    business_name: str,
    reason_now: str,
    proof: str,
    contact_title: str | None = None,
) -> list[dict[str, Any]]:
    """Build a small vetted set of plain, specific first-touch copy arms."""
    business = _text(business_name)
    reason = _text(reason_now).rstrip(".")
    observed_proof = _text(proof).rstrip(".")
    if not business or not reason or not observed_proof:
        raise ValueError("business_name, reason_now and proof are required")

    proof_line = f"Saw {observed_proof}."
    rows = [
        {
            "variant_id": "plain_one_page",
            "body": (
                f"{proof_line}\n\n"
                f"I can put together a one-page view for {business} showing the "
                "commercial opportunities I would check first, using public evidence "
                "rather than guesses.\n\n"
                "Want me to send it?"
            ),
            "cta": "Want me to send it?",
        },
        {
            "variant_id": "direct_observation",
            "body": (
                f"{proof_line}\n\n"
                f"There are a few things I would check next for {business} before "
                "spending more time or money on growth. I can send the short version "
                "with the evidence behind each one.\n\n"
                "Useful if I send that?"
            ),
            "cta": "Useful if I send that?",
        },
        {
            "variant_id": "simple_question",
            "body": (
                f"{proof_line}\n\n"
                "Are you already tracking which outside signals are worth acting on "
                "before they show up in the numbers?\n\n"
                f"I can send the one-page view I would use for {business}. "
                "No deck, just the evidence and the first things I would test."
            ),
            "cta": (
                "Are you already tracking which outside signals are worth acting on "
                "before they show up in the numbers?"
            ),
        },
    ]

    eligible = []
    for row in rows:
        review = review_message(
            subject=f"{_company_token(business)} question",
            body=str(row["body"]),
            cta=str(row["cta"]),
            contact_title=contact_title,
        )
        if review["experiment_eligible"]:
            eligible.append({**row, "quality": review})

    if len(eligible) < 2:
        raise ValueError("insufficient human-quality body variants")
    return eligible



def optimise_first_touch(
    *,
    business_name: str,
    reason_now: str,
    proof: str,
    contact_title: str | None = None,
    territory: str | None = None,
    sender_email: str | None = None,
    brand_domain: str | None = None,
    enterprise_target: bool = False,
) -> dict[str, Any]:
    """Produce evidence-led first-touch copy plus subject tests."""
    business = _text(business_name)
    reason = _text(reason_now).rstrip(".")
    observed_proof = _text(proof).rstrip(".")
    if not business or not reason or not observed_proof:
        raise ValueError("business_name, reason_now and proof are required")

    subjects = build_subject_variants(
        business_name=business,
        reason_now=reason,
        territory=territory,
    )
    subject = subjects[0]["subject"]

    bodies = build_body_variants(
        business_name=business,
        reason_now=reason,
        proof=observed_proof,
        contact_title=contact_title,
    )
    body = str(bodies[0]["body"])
    cta = str(bodies[0]["cta"])
    quality = review_message(
        subject=subject,
        body=body,
        cta=cta,
        contact_title=contact_title,
    )
    sender = review_sender_identity(
        sender_email,
        brand_domain=brand_domain,
        enterprise_target=enterprise_target,
    ) if sender_email or brand_domain else None

    return {
        "subject": subject,
        "subject_variants": subjects[:4],
        "body_variants": bodies,
        "body": body,
        "cta": cta,
        "quality": quality,
        "sender_identity": sender,
        "proof_used": observed_proof,
        "reason_now": reason,
        "invented_claims": False,
        "drafting_only": True,
        "send_enabled": False,
        "execution_authority": "none",
    }
