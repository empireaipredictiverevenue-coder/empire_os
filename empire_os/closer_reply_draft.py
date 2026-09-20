"""Deterministic non-binding closer reply drafts.

These drafts keep a real buyer conversation moving without making pricing,
capacity, exclusivity, payment, fulfilment or revenue commitments.
"""
from __future__ import annotations

from typing import Any, Mapping

POSTAL_ADDRESS = "31 St Thomas St, Bolton, BL1 2QR, UK"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _business(context: Mapping[str, Any]) -> str:
    return _text(context.get("business_name")) or "your team"


def _market(context: Mapping[str, Any]) -> str:
    niche = _text(context.get("niche"))
    metro = _text(context.get("metro"))
    if niche and metro:
        return f"{metro} {niche}"
    return metro or niche or "your market"


def _question_answer(body: str, market: str) -> str:
    lower = body.lower()
    if any(k in lower for k in ("price", "cost", "rate", "pricing")):
        return (
            "Pricing depends on territory, volume, qualification criteria and "
            "whether the pilot is exclusive. I don't want to invent a number "
            "before those are confirmed."
        )
    if any(k in lower for k in ("where", "source", "come from", "get the")):
        return (
            "Empire sources and qualifies opportunities through our own "
            "acquisition/intelligence stack and first-party/public signals; "
            "we do not treat raw scraped contact lists as qualified demand."
        )
    if any(k in lower for k in ("quality", "qualified", "good lead")):
        return (
            "We define the acceptance criteria up front and only route "
            "opportunities that pass qualification and evidence checks."
        )
    if any(k in lower for k in ("exclusive", "exclusivity")):
        return (
            "We can structure a capped or exclusive pilot when the territory, "
            "capacity and economics support it; nothing is assumed until agreed."
        )
    if any(k in lower for k in ("volume", "how many", "quantity")):
        return (
            f"Volume is evidence-based by territory. I can show the current "
            f"{market} picture once we confirm the exact coverage area."
        )
    return (
        "Happy to clarify. I’m referring to verified opportunity flow rather "
        "than a raw contact list. If useful, I can send the short breakdown of "
        "quality criteria, delivery, territory and the pilot structure."
    )


def build_closer_reply(context: Mapping[str, Any]) -> dict[str, str]:
    classification = _text(context.get("classification")).lower()
    if classification not in {"positive", "question", "objection"}:
        raise ValueError("commercial closer reply classification required")

    name = _text(context.get("contact_name"))
    greeting = f"Hi {name.split()[0]}," if name else "Hi,"
    business = _business(context)
    market = _market(context)
    inbound = _text(context.get("reply_body_text"))
    root_subject = _text(context.get("root_subject"))
    subject = root_subject if root_subject.lower().startswith("re:") else f"Re: {root_subject or 'Empire AI'}"

    if classification == "positive":
        message = (
            f"{greeting}\n\n"
            "Thanks for getting back to me. To make sure this is a fit before "
            "we talk commercial terms, could you send me three things: the "
            f"area {business} wants to cover, roughly how many qualified "
            "opportunities per day you could handle, and your preferred "
            "delivery route (email, webhook or phone)?\n\n"
            "Once I have that I can map the current opportunity flow against "
            "your capacity and come back with a small pilot structure."
        )
    elif classification == "question":
        answer = _question_answer(inbound, market)
        message = (
            f"{greeting}\n\n"
            f"{answer}\n\n"
            "If you send your target area and rough daily capacity, I can make "
            "the next reply specific to your operation instead of guessing."
        )
    else:
        message = (
            f"{greeting}\n\n"
            "Fair point. I don't want to force a fit. The cleanest way to test "
            "this is a small bounded pilot with agreed qualification criteria "
            "and no invented volume promises.\n\n"
            "What would need to be true for it to be worth testing for "
            f"{business}: better quality, exclusivity, volume, or the economics?"
        )

    body = (
        message
        + "\n\nBest,\nPhil\nFounder, Empire AI\nempire-ai.co.uk\n\n"
        + POSTAL_ADDRESS
        + "\nIf you’d rather not hear from me, reply “opt out”."
    )
    return {
        "subject": subject,
        "body_text": body,
        "classification": classification,
    }
