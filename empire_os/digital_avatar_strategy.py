"""Evidence-first meeting strategy for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import (
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.predictive_revenue_formula import (
    next_best_action_value,
    predictive_revenue_formula,
)


@dataclass(frozen=True)
class AvatarMeetingStrategyPacket:
    meeting_id: str
    avatar_id: str
    account_name: str
    objective: str
    buyer_signal_summary: str | None
    proof_refs: tuple[str, ...]
    commercial_terms_ref: str | None
    predictive_revenue: Mapping[str, Any]
    next_best_action: Mapping[str, Any]
    blockers: tuple[str, ...]

    mode: str = "OBSERVE"
    execution_authority: str = "none"
    side_effects: str = "none"
    actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["predictive_revenue"] = dict(self.predictive_revenue)
        data["next_best_action"] = dict(self.next_best_action)
        return data


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _refs(values: Sequence[Any] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _text(value)
            for value in (values or ())
            if _text(value)
        )
    )


def build_avatar_meeting_strategy(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    account_name: str,
    objective: str,

    buyer_signal_summary: str | None = None,
    buyer_signal_evidence_refs: Sequence[str] = (),
    proof_refs: Sequence[str] = (),
    commercial_terms_ref: str | None = None,
    predictive_inputs: Mapping[str, Any] | None = None,
    action_candidates: Sequence[Mapping[str, Any]] = (),
) -> AvatarMeetingStrategyPacket:
    identity.validate()
    session.validate()

    if session.avatar_id != identity.avatar_id:
        raise ValueError("avatar session identity mismatch")

    clean_account = _text(account_name)
    clean_objective = _text(objective)
    if not clean_account or not clean_objective:
        raise ValueError("account_name and objective required")

    signal_summary = _text(buyer_signal_summary) or None
    signal_refs = _refs(buyer_signal_evidence_refs)
    proofs = _refs(proof_refs)
    terms_ref = _text(commercial_terms_ref) or None

    blockers: list[str] = []
    if signal_summary and not signal_refs:
        blockers.append("buyer_signal_evidence_missing")
    if not proofs:
        blockers.append("meeting_proof_evidence_missing")

    prediction = predictive_revenue_formula(dict(predictive_inputs or {}))

    if prediction.get("status") != "AVAILABLE":
        blockers.append("predictive_revenue_inputs_incomplete")

    nba = next_best_action_value(action_candidates)
    recommendation = nba.get("recommended_action")
    if not isinstance(recommendation, Mapping):
        blockers.append("next_best_action_unavailable")
        recommendation = {}

    if terms_ref is None:
        blockers.append("verified_commercial_terms_not_bound")

    evidence_refs = _refs((*signal_refs, *proofs, terms_ref))
    if not evidence_refs:
        blockers.append("meeting_evidence_missing")

    return AvatarMeetingStrategyPacket(
        meeting_id=session.meeting_id,
        avatar_id=identity.avatar_id,
        account_name=clean_account,
        objective=clean_objective,
        buyer_signal_summary=signal_summary,
        proof_refs=evidence_refs,
        commercial_terms_ref=terms_ref,
        predictive_revenue=dict(prediction),
        next_best_action=dict(recommendation),
        blockers=tuple(sorted(set(blockers))),
    )
