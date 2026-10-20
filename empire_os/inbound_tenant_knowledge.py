"""Tenant-owned, versioned receptionist knowledge with deterministic abstention.

Knowledge is a customer-approved source, not live tool truth. This module does
not search the web, self-train, infer prices or take booking/payment actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

STOPWORDS = frozenset({
    "a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "is",
    "it", "my", "of", "our", "the", "to", "we", "what", "where", "with", "you", "your",
})
BLOCKED_TOPICS = frozenset({
    "pricing", "availability", "regulated_advice", "payment",
    "refund_decision", "booking_confirmation",
})


def _utc(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("invalid_knowledge_timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("knowledge_timestamp_requires_timezone")
    return moment


def _words(value: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[a-z0-9]+", value.lower())
                     if len(w) > 1 and w not in STOPWORDS)


_SENSITIVE_CLAIM = re.compile(
    r"(?:[£$€]|\b(?:gbp|usd|eur|price|prices|cost|fee|fees|quote|discount|"
    r"refund|paid|payment|availability|available|booked|appointment|"
    r"guarantee|guaranteed|legal|medical)\b)", re.IGNORECASE,
)


def _requires_independent_check(question: str, answer: str) -> bool:
    return bool(_SENSITIVE_CLAIM.search(question) or _SENSITIVE_CLAIM.search(answer))


@dataclass(frozen=True)
class KnowledgeFact:
    tenant_id: str
    fact_id: str
    question: str
    answer: str
    source_ref: str
    reviewed_by: str
    reviewed_at: str
    expires_at: str
    topic: str = "general"
    approved: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        for attr in ("tenant_id", "fact_id", "question", "answer", "source_ref", "reviewed_by"):
            value = getattr(self, attr)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{attr}_required")
        if len(self.answer) > 500:
            raise ValueError("knowledge_answer_too_long")
        if self.topic not in BLOCKED_TOPICS | {"general", "services", "location", "hours"}:
            raise ValueError("unsupported_knowledge_topic")
        if not isinstance(self.approved, bool) or not isinstance(self.synthetic, bool):
            raise ValueError("invalid_knowledge_approval_flag")
        start = _utc(self.reviewed_at)
        end = _utc(self.expires_at)
        if end <= start or end - start > timedelta(days=180):
            raise ValueError("invalid_knowledge_review_window")


@dataclass(frozen=True)
class TenantKnowledgePack:
    tenant_id: str
    business_name: str
    version: int
    facts: tuple[KnowledgeFact, ...]
    activated: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.business_name.strip():
            raise ValueError("tenant_and_business_required")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("knowledge_version_required")
        if not isinstance(self.activated, bool):
            raise ValueError("invalid_pack_activation")
        seen: set[str] = set()
        for fact in self.facts:
            if fact.tenant_id != self.tenant_id:
                raise ValueError("cross_tenant_knowledge_fact")
            if fact.fact_id in seen:
                raise ValueError("duplicate_knowledge_fact_id")
            seen.add(fact.fact_id)


@dataclass(frozen=True)
class KnowledgeAnswer:
    status: str
    spoken_text: str
    evidence_refs: tuple[str, ...] = ()
    fact_id: str | None = None
    match_coverage: float | None = None
    pack_version: int | None = None
    customer_contact_authorized: bool = False
    booking_confirmed: bool = False
    payment_authorized: bool = False


def answer_from_knowledge(
    pack: TenantKnowledgePack, question: str, *,
    as_of: datetime, simulated: bool = False,
) -> KnowledgeAnswer:
    """Answer approved general FAQ only, or explicitly abstain.

    All lower-case scores are deterministic lexical overlap and should NEVER
    be interpreted as model confidence, accuracy, or revenue probability.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("knowledge_as_of_timezone_required")
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("question_required")
    base = "I am " + pack.business_name + "'s AI assistant. "
    if not pack.activated:
        return KnowledgeAnswer(
            "not_activated", base + "I can't verify the answer yet. Please ask the team.",
            pack_version=pack.version,
        )
    terms = _words(question)
    if not terms:
        return KnowledgeAnswer(
            "insufficient_evidence", base + "Could you tell me more about your question?",
            pack_version=pack.version,
        )
    eligible: list[tuple[float, KnowledgeFact]] = []
    blocked_candidates = 0
    for fact in pack.facts:
        if (not fact.approved or (fact.synthetic and not simulated)
            or not _utc(fact.reviewed_at) <= as_of <= _utc(fact.expires_at)):
            continue
        match = len(terms & _words(fact.question)) / len(terms)
        if match < 0.75:
            continue
        if fact.topic in BLOCKED_TOPICS or _requires_independent_check(fact.question, fact.answer):
            blocked_candidates += 1
        else:
            eligible.append((match, fact))
    if blocked_candidates:
        return KnowledgeAnswer(
            "needs_human_review",
            base + "A team member needs to verify that information before I can answer.",
            pack_version=pack.version,
        )
    if not eligible:
        return KnowledgeAnswer(
            "insufficient_evidence",
            base + "I don't have a verified answer to that question. Please ask the team.",
            pack_version=pack.version,
        )
    eligible.sort(key=lambda item: (-item[0], item[1].fact_id))
    best_score = eligible[0][0]
    tied = [fact for score, fact in eligible if score == best_score]
    if len({fact.answer for fact in tied}) > 1:
        return KnowledgeAnswer(
            "ambiguous",
            base + "I need the team to clarify that before I give you an answer.",
            pack_version=pack.version,
        )
    winner = tied[0]
    return KnowledgeAnswer(
        "approved_fact",
        base + winner.answer,
        evidence_refs=(winner.source_ref,),
        fact_id=winner.fact_id,
        match_coverage=round(best_score, 2),
        pack_version=pack.version,
    )
