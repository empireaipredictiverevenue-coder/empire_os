"""Adaptive, evidence-only subject/body selection for governed outreach."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.experiment_engine import (
    ExperimentDefinition,
    plan_assignment,
)


SNAPSHOT_PATH = Path(
    "runtime/outreach_optimizer/latest.json"
)
MIN_DELIVERED_PER_ARM = 8
SEGMENT_MIN_DELIVERED = 16
EXPLORATION_FRACTION = 0.20
COMMERCIAL_REPLY_CLASSES = frozenset({
    "positive",
    "question",
    "objection",
    "later",
})
LEARNING_DIMENSIONS = (
    "problem_class", "trigger_class", "proof_class", "cta_strategy",
    "followup_step", "locale", "timezone",
)
FUNNEL_STAGES = (
    "qualified_conversation", "commercial_terms", "order", "verified_payment",
    "fulfilled", "recognized_revenue",
)

STOP_REPLY_CLASSES = frozenset({
    "negative",
    "unsubscribe",
})


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(value: Any) -> str:
    return _text(value).lower().replace(" ", "_")


def segment_key(
    *,
    offer_key: Any,
    niche: Any,
    decision_role: Any,
    dimensions: Mapping[str, Any] | None = None,
) -> str:
    base = "|".join((
        _norm(offer_key) or "unknown_offer",
        _norm(niche) or "unknown_niche",
        _norm(decision_role) or "unknown_role",
    ))
    known = dimensions if isinstance(dimensions, Mapping) else {}
    suffix = [f"{key}={_norm(known[key])}" for key in LEARNING_DIMENSIONS if _text(known.get(key))]
    return "|".join([base, *suffix])


def load_snapshot(
    repo_root: str | Path = "/srv/empire_os",
) -> dict[str, Any]:
    path = Path(repo_root).resolve() / SNAPSHOT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _arm_stats(
    snapshot: Mapping[str, Any],
    *,
    segment: str,
    arm_type: str,
) -> dict[str, Mapping[str, Any]]:
    segments = snapshot.get("segments")
    if not isinstance(segments, Mapping):
        return {}
    row = segments.get(segment)
    if not isinstance(row, Mapping):
        return {}
    arms = row.get(arm_type)
    if not isinstance(arms, Mapping):
        return {}
    return {
        str(key): value
        for key, value in arms.items()
        if isinstance(value, Mapping)
    }


def _segment_delivered(
    snapshot: Mapping[str, Any],
    segment: str,
) -> int:
    segments = snapshot.get("segments")
    if not isinstance(segments, Mapping):
        return 0
    row = segments.get(segment)
    if not isinstance(row, Mapping):
        return 0
    try:
        return int(row.get("delivered") or 0)
    except (TypeError, ValueError):
        return 0


def _preferred_segment(
    snapshot: Mapping[str, Any],
    exact_segment: str,
) -> str:
    if _segment_delivered(snapshot, exact_segment) >= SEGMENT_MIN_DELIVERED:
        return exact_segment
    return "__global__"


def _arm_score(row: Mapping[str, Any]) -> float:
    delivered = max(int(row.get("delivered") or 0), 0)
    commercial = max(int(row.get("commercial_replies") or 0), 0)
    stops = max(int(row.get("stop_replies") or 0), 0)
    # Conservative shrinkage toward zero while samples are small.
    denominator = delivered + 12.0
    return (commercial - 2.0 * stops) / denominator


def _mature(
    stats: Mapping[str, Mapping[str, Any]],
    arm_ids: Iterable[str],
) -> bool:
    rows = [
        stats.get(arm_id, {})
        for arm_id in arm_ids
    ]
    qualified = sum(
        int(row.get("delivered") or 0) >= MIN_DELIVERED_PER_ARM
        for row in rows
    )
    return qualified >= 2


def _bucket(key: str) -> int:
    return int(sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 10_000


def _balanced_arm(
    arm_ids: tuple[str, ...],
    *,
    assignment_key: str,
    experiment_id: str,
) -> str:
    if not arm_ids:
        raise ValueError("at least one arm required")
    if len(arm_ids) == 1:
        return arm_ids[0]
    definition = ExperimentDefinition(
        experiment_id=experiment_id,
        hypothesis="Observed outreach response differs by message arm.",
        metric="commercial_conversation_rate",
        control_variant=arm_ids[0],
        treatment_variants=tuple(arm_ids[1:]),
        holdout_fraction=0.0,
        minimum_sample_size=MIN_DELIVERED_PER_ARM,
    )
    return plan_assignment(
        definition,
        subject_key=assignment_key,
    ).arm


def _choose_arm(
    arm_ids: tuple[str, ...],
    *,
    assignment_key: str,
    arm_type: str,
    snapshot: Mapping[str, Any],
    exact_segment: str,
) -> tuple[str, dict[str, Any]]:
    if not arm_ids:
        raise ValueError(f"{arm_type} arms required")
    segment = _preferred_segment(snapshot, exact_segment)
    stats = _arm_stats(
        snapshot,
        segment=segment,
        arm_type=arm_type,
    )
    if segment != "__global__" and not _mature(stats, arm_ids):
        broader = _arm_stats(snapshot, segment="__global__", arm_type=arm_type)
        if _mature(broader, arm_ids):
            segment, stats = "__global__", broader
    if not _mature(stats, arm_ids):
        arm = _balanced_arm(
            arm_ids,
            assignment_key=assignment_key,
            experiment_id=f"outreach-{arm_type}-v1",
        )
        return arm, {
            "mode": "balanced_learning",
            "segment": segment,
            "mature": False,
            "exploration": True,
        }

    explore = (
        _bucket(f"explore:{arm_type}:{assignment_key}") <
        int(EXPLORATION_FRACTION * 10_000)
    )
    if explore:
        arm = _balanced_arm(
            arm_ids,
            assignment_key=f"explore:{assignment_key}",
            experiment_id=f"outreach-{arm_type}-explore-v1",
        )
        mode = "adaptive_exploration"
    else:
        arm = max(
            tuple(item for item in arm_ids if int(stats.get(item, {}).get("delivered") or 0) >= MIN_DELIVERED_PER_ARM),
            key=lambda item: (
                _arm_score(stats.get(item, {})),
                int(stats.get(item, {}).get("commercial_replies") or 0),
                -int(stats.get(item, {}).get("stop_replies") or 0),
                item == arm_ids[0],
            ),
        )
        mode = "adaptive_exploit"
    return arm, {
        "mode": mode,
        "segment": segment,
        "mature": True,
        "exploration": explore,
        "scores": {
            item: round(_arm_score(stats.get(item, {})), 6)
            for item in arm_ids
        },
    }


def build_subject_arm_candidates(
    subjects: Iterable[str],
    *,
    business_name: Any,
    territory: Any = None,
) -> list[dict[str, str]]:
    """Map concrete subject strings onto stable style IDs across copy versions."""
    business_words = [
        part.lower()
        for part in _text(business_name).replace("/", " ").split()
        if part
    ]
    company_token = business_words[0] if business_words else ""
    territory_text = _text(territory).lower()
    rows: list[dict[str, str]] = []
    used: set[str] = set()

    for index, raw in enumerate(subjects):
        subject = _text(raw)
        if not subject:
            continue
        lower = subject.lower()
        if lower.startswith("one thing on "):
            arm = "one_thing"
        elif " / " in subject:
            arm = "territory_company"
        elif lower.startswith("quick ") and lower.endswith(" question"):
            arm = "quick_question"
        elif lower.endswith(" question"):
            arm = "company_question"
        elif "commercial signals" in lower:
            arm = "commercial_signals"
        elif territory_text and lower.startswith(territory_text):
            arm = "territory_topic"
        elif "customer signals" in lower or "growth signals" in lower:
            arm = "company_topic"
        elif company_token and lower == company_token:
            arm = "company_only"
        elif len(subject.split()) == 1:
            arm = "company_only"
        else:
            arm = f"subject_style_{index}"

        if arm in used:
            arm = f"{arm}_{index}"
        used.add(arm)
        rows.append({
            "variant_id": arm,
            "subject": subject,
        })
    return rows


def build_body_arm_candidates(
    *,
    business_name: Any,
    observed_evidence: Any,
) -> list[dict[str, str]]:
    """Build fixed plain-English body styles from observed evidence only."""
    business = _text(business_name)
    proof = _text(observed_evidence).rstrip(".")
    if not business or not proof:
        raise ValueError(
            "business_name and observed_evidence required for adaptive copy"
        )
    proof_line = f"Saw {proof}."
    return [
        {
            "variant_id": "plain_one_page",
            "core_body": (
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
            "core_body": (
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
            "core_body": (
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


def select_message_arms(
    *,
    assignment_key: str,
    subject_arm_ids: Iterable[str],
    body_arm_ids: Iterable[str],
    offer_key: Any,
    niche: Any,
    decision_role: Any,
    snapshot: Mapping[str, Any] | None = None,
    dimensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    key = _text(assignment_key)
    if not key:
        raise ValueError("assignment_key required")
    subjects = tuple(dict.fromkeys(
        str(value).strip()
        for value in subject_arm_ids
        if str(value).strip()
    ))
    bodies = tuple(dict.fromkeys(
        str(value).strip()
        for value in body_arm_ids
        if str(value).strip()
    ))
    exact = segment_key(
        offer_key=offer_key,
        niche=niche,
        decision_role=decision_role,
        dimensions=dimensions,
    )
    state = snapshot if isinstance(snapshot, Mapping) else {}
    subject_arm, subject_meta = _choose_arm(
        subjects,
        assignment_key=key,
        arm_type="subject_arms",
        snapshot=state,
        exact_segment=exact,
    )
    body_arm, body_meta = _choose_arm(
        bodies,
        assignment_key=key,
        arm_type="body_arms",
        snapshot=state,
        exact_segment=exact,
    )
    return {
        "schema_version": "empire.adaptive-outreach-selection.v1",
        "assignment_key": key,
        "exact_segment": exact,
        "learning_dimensions": {key: dimensions[key] for key in LEARNING_DIMENSIONS if dimensions and _text(dimensions.get(key))},
        "subject_arm": subject_arm,
        "body_arm": body_arm,
        "subject_selection": subject_meta,
        "body_selection": body_meta,
        "minimum_delivered_per_arm": MIN_DELIVERED_PER_ARM,
        "exploration_fraction": EXPLORATION_FRACTION,
        "uses_open_tracking": False,
        "execution_authority": "copy_selection_only",
    }


@dataclass
class _Counts:
    intents: int = 0
    delivered: int = 0
    replies: int = 0
    commercial_replies: int = 0
    stop_replies: int = 0
    positive_replies: int = 0
    negative_replies: int = 0
    unsubscribes: int = 0
    qualified_conversation: int = 0
    commercial_terms: int = 0
    order: int = 0
    verified_payment: int = 0
    fulfilled: int = 0
    recognized_revenue: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "intents": self.intents,
            "delivered": self.delivered,
            "replies": self.replies,
            "commercial_replies": self.commercial_replies,
            "stop_replies": self.stop_replies,
            "positive_replies": self.positive_replies,
            "negative_replies": self.negative_replies,
            "unsubscribes": self.unsubscribes,
            **{stage: getattr(self, stage) for stage in FUNNEL_STAGES},
            "commercial_reply_rate": (
                round(self.commercial_replies / self.delivered, 6)
                if self.delivered else None
            ),
            "stop_reply_rate": (
                round(self.stop_replies / self.delivered, 6)
                if self.delivered else None
            ),
        }


def build_performance_snapshot(
    records: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    segments: dict[str, dict[str, Any]] = {}
    labelled = 0
    unlabelled = 0
    rejected_feedback = 0
    seen_intents: set[str] = set()
    seen_outcomes: set[str] = set()
    seen_middle_stages: set[str] = set()

    def ensure_segment(key: str) -> dict[str, Any]:
        return segments.setdefault(key, {
            "delivered": 0,
            "subject_arms": {},
            "body_arms": {},
        })

    for raw in records:
        intent_id = _text(raw.get("intent_id"))
        if intent_id and intent_id in seen_intents:
            continue
        if intent_id:
            seen_intents.add(intent_id)
        metadata = raw.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        adaptive = metadata.get("adaptive_outreach")
        if not isinstance(adaptive, Mapping):
            unlabelled += 1
            continue
        subject_arm = _text(adaptive.get("subject_arm"))
        body_arm = _text(adaptive.get("body_arm"))
        exact = _text(adaptive.get("exact_segment"))
        if not subject_arm or not body_arm or not exact:
            unlabelled += 1
            continue
        labelled += 1
        delivered = bool(raw.get("delivered"))
        classification = _norm(raw.get("classification"))

        # Terminal economic evidence enters only through the existing V2B gate.
        downstream = {stage: False for stage in FUNNEL_STAGES}
        feedback = raw.get("verified_outcome_feedback")
        if isinstance(feedback, Mapping):
            from empire_os.outcome_feedback import validate_verified_feedback
            try:
                validate_verified_feedback(feedback, tenant_id=raw.get("tenant_id"), as_of=generated_at)
            except (ValueError, TypeError, KeyError):
                rejected_feedback += 1
            else:
                # Require explicit recipient/order attribution; never join on a reply label.
                if (raw.get("fulfilment_order_id") and
                        raw.get("fulfilment_order_id") == feedback.get("fulfilment_order_id")):
                    outcome_ref = _text(feedback.get("outcome_ref"))
                    if (outcome_ref not in seen_outcomes and feedback.get("actual_revenue") is True
                            and feedback.get("verified_label") == 1):
                        seen_outcomes.add(outcome_ref)
                        for stage in ("order", "verified_payment", "fulfilled", "recognized_revenue"):
                            downstream[stage] = True
        from datetime import datetime
        from empire_os.conversation_qualification import validate_qualified_conversation_stage
        from empire_os.commercial_terms_materializer import validate_commercial_terms_stage
        for stage, validate in (("qualified_conversation", validate_qualified_conversation_stage),
                                ("commercial_terms", validate_commercial_terms_stage)):
            evidence = raw.get(stage + "_evidence")
            if not isinstance(evidence, Mapping):
                continue
            try:
                validate(evidence, raw, as_of=datetime.fromisoformat(generated_at.replace("Z", "+00:00")))
            except (ValueError, TypeError, KeyError):
                continue
            ref = evidence["stage_ref"]
            if ref not in seen_middle_stages:
                seen_middle_stages.add(ref)
                downstream[stage] = True
        for key in dict.fromkeys((exact, "__global__")):
            segment = ensure_segment(key)
            if delivered:
                segment["delivered"] += 1
            for group, arm_id in (
                ("subject_arms", subject_arm),
                ("body_arms", body_arm),
            ):
                counts = segment[group].setdefault(
                    arm_id,
                    _Counts(),
                )
                counts.intents += 1
                if delivered:
                    counts.delivered += 1
                for stage, verified in downstream.items():
                    if verified:
                        setattr(counts, stage, getattr(counts, stage) + 1)
                if classification in COMMERCIAL_REPLY_CLASSES | STOP_REPLY_CLASSES | {"other"}:
                    counts.replies += 1
                    if classification in COMMERCIAL_REPLY_CLASSES:
                        counts.commercial_replies += 1
                    if classification == "positive":
                        counts.positive_replies += 1
                    if classification == "negative":
                        counts.negative_replies += 1
                    if classification == "unsubscribe":
                        counts.unsubscribes += 1
                    if classification in STOP_REPLY_CLASSES:
                        counts.stop_replies += 1

    serialised: dict[str, Any] = {}
    for key, segment in segments.items():
        serialised[key] = {
            "delivered": segment["delivered"],
            "subject_arms": {
                arm: counts.as_dict()
                for arm, counts in segment["subject_arms"].items()
            },
            "body_arms": {
                arm: counts.as_dict()
                for arm, counts in segment["body_arms"].items()
            },
        }

    return {
        "schema_version": "empire.adaptive-outreach-performance.v1",
        "generated_at": generated_at,
        "minimum_delivered_per_arm": MIN_DELIVERED_PER_ARM,
        "segment_min_delivered": SEGMENT_MIN_DELIVERED,
        "exploration_fraction": EXPLORATION_FRACTION,
        "labelled_intent_count": labelled,
        "unlabelled_history_count": unlabelled,
        "segments": serialised,
        "winner_claim_allowed": any(
            _mature(
                row.get("subject_arms", {}),
                tuple(row.get("subject_arms", {}).keys()),
            )
            or _mature(
                row.get("body_arms", {}),
                tuple(row.get("body_arms", {}).keys()),
            )
            for row in serialised.values() if row["delivered"] >= SEGMENT_MIN_DELIVERED
        ),
        "rejected_outcome_feedback_count": rejected_feedback,
        "downstream_stage_policy": "canonical_middle_stage_evidence + verified_outcome_feedback; no reply-derived stages",
        "unavailable_stage_sources": [],
        "middle_stage_sources": {"qualified_conversation": "closer_events.state_advanced.qualified", "commercial_terms": "approved installed review + commercial_terms_events"},
        "expected_economics_is_prediction": True,
        "uses_open_tracking": False,
        "canonical_truth": "EmpireDB outbound events + classified replies",
        "execution_authority": "none",
    }
