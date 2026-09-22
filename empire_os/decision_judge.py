"""Empire Decision Judge: fast typed judgment for Voice/Revenue OS.

The judge is intentionally deterministic by default:
- no network dependency
- no generative prose
- typed actions and intents
- fail-closed on critical transcript ambiguity
- designed to reconcile multiple ASR candidates

It does not execute suppression, payments, outreach, or commercial actions.
It only returns a decision envelope for the caller.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import time
from typing import Any, Iterable


SCHEMA_VERSION = "empire.decision_judge.v1"

ACTION_CONTINUE = "continue"
ACTION_CLARIFY = "clarify"
ACTION_STOP = "stop"
ACTION_HUMAN_HANDOFF = "human_handoff"

INTENT_UNKNOWN = "unknown"
INTENT_OPT_OUT = "opt_out"
INTENT_NOT_INTERESTED = "not_interested"
INTENT_INTERESTED = "interested"
INTENT_WRONG_PERSON = "wrong_person"
INTENT_DECISION_MAKER = "decision_maker"
INTENT_FOLLOW_UP = "follow_up_permission"
INTENT_PRICING = "pricing_or_terms"
INTENT_PAYMENT = "payment_or_commitment"

OPT_OUT_PATTERNS = (
    r"\bdo not call\b",
    r"\bdon['’]?t call\b",
    r"\bstop calling\b",
    r"\bstop call(?:ing|s)?\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bdo not contact\b",
    r"\bdon['’]?t contact\b",
    r"\bnever call\b",
    r"\bno more calls\b",
)

NEGATIVE_PATTERNS = (
    r"\bnot interested\b",
    r"\bno thanks\b",
    r"\bno thank you\b",
    r"\bnot for me\b",
    r"\bnot right now\b",
    r"\bnot now\b",
    r"\bno need\b",
)

INTEREST_PATTERNS = (
    r"\bi(?:'| a)m interested\b",
    r"\binterested\b",
    r"\bsend (?:it|that|the brief|me)\b",
    r"\bsounds good\b",
    r"\btell me more\b",
    r"\blet['’]?s talk\b",
    r"\byes[, ]+(?:please|send|sure)\b",
)

WRONG_PERSON_PATTERNS = (
    r"\bwrong person\b",
    r"\bnot the person\b",
    r"\bi don['’]?t handle\b",
    r"\bi do not handle\b",
    r"\bnot my department\b",
    r"\bspeak to\b.+\binstead\b",
)

DECISION_MAKER_PATTERNS = (
    r"\bi handle (?:growth|sales|marketing|revenue|new business)\b",
    r"\bi(?:'| a)m responsible for\b",
    r"\bthat['’]?s me\b",
    r"\bi am the owner\b",
    r"\bi(?:'| a)m the owner\b",
)

FOLLOW_UP_PATTERNS = (
    r"\bsend (?:me )?(?:an? |the )?(?:email|brief|details|information)\b",
    r"\bsend (?:it|that|the brief) (?:to me )?(?:by )?email\b",
    r"\bfollow up\b",
    r"\bcall me (?:back|later)\b",
    r"\bemail me\b",
)

PRICING_PATTERNS = (
    r"\bhow much\b",
    r"\bwhat does (?:it|that|this) cost\b",
    r"\bprice\b",
    r"\bpricing\b",
    r"\bcost\b",
    r"\bterms\b",
)

PAYMENT_PATTERNS = (
    r"\bi['’]?ll pay\b",
    r"\bwe['’]?ll pay\b",
    r"\bcharge (?:me|us)\b",
    r"\btake payment\b",
    r"\bpay now\b",
    r"\baccept (?:the )?(?:deal|offer|terms)\b",
    r"\bagree to (?:the )?terms\b",
)

TEMPORAL_NOW_PATTERNS = (
    r"\bright now\b",
    r"\bfrom now\b",
    r"\bnow that\b",
    r"\bnow i\b",
    r"\bnow we\b",
    r"\bnow you\b",
    r"\bnow they\b",
    r"\bnow is\b",
)

MONTH_WORDS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
DAY_WORDS = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)
RELATIVE_DATE_WORDS = (
    "today", "tomorrow", "tonight", "yesterday", "next week",
    "next month", "this week", "this month",
)


@dataclass(frozen=True)
class TranscriptCandidate:
    source: str
    text: str
    confidence: float | None = None


@dataclass
class DecisionJudgeResult:
    action: str
    intent: str
    confidence: float
    risk_level: str
    requires_clarification: bool
    suppression_requested: bool
    commercial_authority: bool
    route: str
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)
    candidate_count: int = 0
    latency_ms: float = 0.0
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(value: str) -> str:
    text = str(value or "").lower().replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _matches(text: str, patterns: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            hits.append(match.group(0))
    return hits


def _numbers(text: str) -> set[str]:
    return {
        value.replace(",", "")
        for value in re.findall(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", text)
    }


def _money(text: str) -> set[str]:
    found = set(
        match.group(0).lower().replace(",", "")
        for match in re.finditer(
            r"(?:[$£€]\s*\d+(?:[.,]\d+)?|"
            r"\b\d+(?:[.,]\d+)?\s*(?:pounds?|dollars?|euros?|usd|gbp|usdt)\b)",
            text,
            flags=re.IGNORECASE,
        )
    )
    return found


def _dates(text: str) -> set[str]:
    lower = _norm(text)
    found = {
        word for word in MONTH_WORDS + DAY_WORDS + RELATIVE_DATE_WORDS
        if word in lower
    }
    found.update(
        re.findall(
            r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
            lower,
        )
    )
    return found


def _has_possible_no_now_flip(text: str) -> bool:
    lower = _norm(text)
    if not re.search(r"\bnow\b", lower):
        return False
    if _matches(lower, TEMPORAL_NOW_PATTERNS):
        return False
    # "now" before a noun/adjective phrase is a common ASR corruption of "no".
    return bool(
        re.search(
            r"(?:^|[.!?]\s+|,\s+)now\s+[a-z][a-z-]+",
            lower,
        )
        or re.search(r"\bnow\s+external\b", lower)
    )


def _critical_signature(text: str) -> dict[str, Any]:
    lower = _norm(text)
    return {
        "opt_out": bool(_matches(lower, OPT_OUT_PATTERNS)),
        "negative": bool(_matches(lower, NEGATIVE_PATTERNS)),
        "interest": bool(_matches(lower, INTEREST_PATTERNS)),
        "wrong_person": bool(_matches(lower, WRONG_PERSON_PATTERNS)),
        "decision_maker": bool(_matches(lower, DECISION_MAKER_PATTERNS)),
        "follow_up": bool(_matches(lower, FOLLOW_UP_PATTERNS)),
        "pricing": bool(_matches(lower, PRICING_PATTERNS)),
        "payment": bool(_matches(lower, PAYMENT_PATTERNS)),
        "numbers": sorted(_numbers(lower)),
        "money": sorted(_money(lower)),
        "dates": sorted(_dates(lower)),
        "possible_no_now_flip": _has_possible_no_now_flip(lower),
    }


class EmpireDecisionJudge:
    """Fast, typed, fail-closed decision layer."""

    def judge_text(
        self,
        text: str,
        *,
        source: str = "unknown",
        confidence: float | None = None,
    ) -> DecisionJudgeResult:
        return self.judge_candidates([
            TranscriptCandidate(
                source=source,
                text=text,
                confidence=confidence,
            )
        ])

    def judge_candidates(
        self,
        candidates: Iterable[TranscriptCandidate | dict[str, Any]],
    ) -> DecisionJudgeResult:
        started = time.perf_counter()
        parsed: list[TranscriptCandidate] = []
        for item in candidates:
            if isinstance(item, TranscriptCandidate):
                candidate = item
            else:
                candidate = TranscriptCandidate(
                    source=str(item.get("source") or "unknown"),
                    text=str(item.get("text") or ""),
                    confidence=(
                        float(item["confidence"])
                        if item.get("confidence") is not None
                        else None
                    ),
                )
            if _norm(candidate.text):
                parsed.append(candidate)

        if not parsed:
            return self._result(
                started,
                action=ACTION_CLARIFY,
                intent=INTENT_UNKNOWN,
                confidence=0.0,
                risk_level="medium",
                requires_clarification=True,
                suppression_requested=False,
                route="clarifier",
                reasons=["no_usable_transcript"],
                risk_flags=["empty_transcript"],
                candidates=parsed,
                signatures=[],
            )

        signatures = [_critical_signature(item.text) for item in parsed]
        texts = [_norm(item.text) for item in parsed]

        evidence: list[str] = []
        reasons: list[str] = []
        risk_flags: list[str] = []

        for text in texts:
            evidence.extend(_matches(text, OPT_OUT_PATTERNS))
            evidence.extend(_matches(text, NEGATIVE_PATTERNS))
            evidence.extend(_matches(text, INTEREST_PATTERNS))
            evidence.extend(_matches(text, WRONG_PERSON_PATTERNS))
            evidence.extend(_matches(text, FOLLOW_UP_PATTERNS))
            evidence.extend(_matches(text, PRICING_PATTERNS))
            evidence.extend(_matches(text, PAYMENT_PATTERNS))

        if any(sig["opt_out"] for sig in signatures):
            return self._result(
                started,
                action=ACTION_STOP,
                intent=INTENT_OPT_OUT,
                confidence=0.99,
                risk_level="critical",
                requires_clarification=False,
                suppression_requested=True,
                route="suppression",
                reasons=["explicit_opt_out_detected"],
                risk_flags=["contact_suppression_required"],
                evidence=evidence,
                candidates=parsed,
                signatures=signatures,
            )

        disagreement_fields = (
            "negative",
            "interest",
            "wrong_person",
            "decision_maker",
            "follow_up",
            "pricing",
            "payment",
        )
        disagreements: list[str] = []
        if len(signatures) > 1:
            for key in disagreement_fields:
                values = {bool(sig[key]) for sig in signatures}
                if len(values) > 1:
                    disagreements.append(key)
            for key in ("numbers", "money", "dates"):
                values = {tuple(sig[key]) for sig in signatures}
                if len(values) > 1:
                    disagreements.append(key)

        if disagreements:
            reasons.append("critical_asr_disagreement")
            risk_flags.extend(
                f"asr_disagreement:{field}" for field in disagreements
            )

        if any(sig["possible_no_now_flip"] for sig in signatures):
            reasons.append("possible_no_now_semantic_flip")
            risk_flags.append("possible_negation_flip")

        if reasons:
            return self._result(
                started,
                action=ACTION_CLARIFY,
                intent=INTENT_UNKNOWN,
                confidence=0.45,
                risk_level="high",
                requires_clarification=True,
                suppression_requested=False,
                route="clarifier",
                reasons=reasons,
                risk_flags=risk_flags,
                evidence=evidence,
                candidates=parsed,
                signatures=signatures,
            )

        if any(sig["payment"] for sig in signatures):
            return self._result(
                started,
                action=ACTION_HUMAN_HANDOFF,
                intent=INTENT_PAYMENT,
                confidence=0.94,
                risk_level="high",
                requires_clarification=False,
                suppression_requested=False,
                route="commercial_handoff",
                reasons=["binding_or_payment_language_detected"],
                risk_flags=["commercial_authority_required"],
                evidence=evidence,
                candidates=parsed,
                signatures=signatures,
            )

        if any(sig["negative"] for sig in signatures):
            return self._result(
                started,
                action=ACTION_STOP,
                intent=INTENT_NOT_INTERESTED,
                confidence=0.93,
                risk_level="low",
                requires_clarification=False,
                suppression_requested=False,
                route="end_conversation",
                reasons=["clear_disinterest_detected"],
                evidence=evidence,
                candidates=parsed,
                signatures=signatures,
            )

        if any(sig["wrong_person"] for sig in signatures):
            intent = INTENT_WRONG_PERSON
            confidence = 0.92
        elif any(sig["decision_maker"] for sig in signatures):
            intent = INTENT_DECISION_MAKER
            confidence = 0.9
        elif any(sig["follow_up"] for sig in signatures):
            intent = INTENT_FOLLOW_UP
            confidence = 0.92
        elif any(sig["pricing"] for sig in signatures):
            intent = INTENT_PRICING
            confidence = 0.88
        elif any(sig["interest"] for sig in signatures):
            intent = INTENT_INTERESTED
            confidence = 0.9
        else:
            intent = INTENT_UNKNOWN
            confidence = 0.72

        return self._result(
            started,
            action=ACTION_CONTINUE,
            intent=intent,
            confidence=confidence,
            risk_level="low",
            requires_clarification=False,
            suppression_requested=False,
            route="closer",
            reasons=["safe_to_continue"],
            evidence=evidence,
            candidates=parsed,
            signatures=signatures,
        )

    @staticmethod
    def _result(
        started: float,
        *,
        action: str,
        intent: str,
        confidence: float,
        risk_level: str,
        requires_clarification: bool,
        suppression_requested: bool,
        route: str,
        reasons: list[str],
        candidates: list[TranscriptCandidate],
        signatures: list[dict[str, Any]],
        risk_flags: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> DecisionJudgeResult:
        latency_ms = (time.perf_counter() - started) * 1000
        return DecisionJudgeResult(
            action=action,
            intent=intent,
            confidence=round(max(0.0, min(confidence, 1.0)), 3),
            risk_level=risk_level,
            requires_clarification=requires_clarification,
            suppression_requested=suppression_requested,
            commercial_authority=False,
            route=route,
            reasons=list(dict.fromkeys(reasons)),
            risk_flags=list(dict.fromkeys(risk_flags or [])),
            evidence=list(dict.fromkeys(evidence or []))[:12],
            signals={
                "sources": [item.source for item in candidates],
                "signatures": signatures,
            },
            candidate_count=len(candidates),
            latency_ms=round(latency_ms, 3),
        )
