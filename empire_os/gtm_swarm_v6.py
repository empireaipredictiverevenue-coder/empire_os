"""Native multi-niche GTM swarm planning for EmpireOS.

This module salvages the useful parts of the historical open-source GTM swarm
blueprint without introducing a parallel execution bus. It is deterministic,
evidence-first, multi-niche, and hands execution to the existing governed GTM
and outbound systems.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from empire_os.niche_taxonomy import niche_family


LEAD_MAGNETS = {
    "revenue_leak_audit": {
        "title": "Instant Revenue / Performance Leak Audit",
        "intent_classes": {"commercial", "problem", "product"},
        "requires_event_signal": False,
    },
    "live_event_radar": {
        "title": "Live Event / Disruption Radar",
        "intent_classes": {"event_trigger", "territory"},
        "requires_event_signal": True,
    },
    "competitor_stack_calculator": {
        "title": "Competitor Stack & Cost Replacement Calculator",
        "intent_classes": {"comparison", "commercial"},
        "requires_event_signal": False,
    },
}

ENGAGEMENT_WEIGHTS = {
    "email_open": 1,
    "link_click": 4,
    "landing_view": 2,
    "lead_magnet_started": 5,
    "lead_magnet_completed": 12,
    "pricing_view": 8,
    "reply_positive": 20,
    "reply_question": 12,
    "reply_objection": 7,
    "unsubscribe": -100,
    "bounce": -100,
}


@dataclass(frozen=True)
class NicheConfig:
    niche: str
    icp_key: str
    target_metros: tuple[str, ...]
    score_threshold: int = 70
    allowed_channels: tuple[str, ...] = ("email",)
    preferred_lead_magnets: tuple[str, ...] = (
        "revenue_leak_audit",
        "live_event_radar",
        "competitor_stack_calculator",
    )

    def validate(self) -> None:
        if not str(self.niche or "").strip():
            raise ValueError("niche required")
        if not str(self.icp_key or "").strip():
            raise ValueError("icp_key required")
        if not 0 <= int(self.score_threshold) <= 100:
            raise ValueError("score_threshold must be 0-100")
        if not self.allowed_channels:
            raise ValueError("allowed_channels required")
        unsupported = set(self.allowed_channels) - {"email", "sms", "phone"}
        if unsupported:
            raise ValueError(
                "unsupported allowed channel(s): "
                + ", ".join(sorted(unsupported))
            )
        unknown = set(self.preferred_lead_magnets) - set(LEAD_MAGNETS)
        if unknown:
            raise ValueError(
                "unknown lead magnet(s): " + ", ".join(sorted(unknown))
            )


@dataclass(frozen=True)
class GtmLeadEvidence:
    prospect_id: str
    niche: str
    metro: str | None
    score: int | None
    score_evidence_ref: str | None
    intent_class: str | None
    intent_evidence_refs: tuple[str, ...]
    contact_ready: bool
    outreach_ready: bool
    event_signal_observed: bool = False

    def validate(self) -> None:
        if not str(self.prospect_id or "").strip():
            raise ValueError("prospect_id required")
        if self.score is not None and not 0 <= int(self.score) <= 100:
            raise ValueError("score must be 0-100")


@dataclass(frozen=True)
class EngagementEvent:
    event_type: str
    evidence_ref: str
    observed_at: str

    def validate(self) -> None:
        if self.event_type not in ENGAGEMENT_WEIGHTS:
            raise ValueError(f"unsupported engagement event: {self.event_type}")
        if not str(self.evidence_ref or "").strip():
            raise ValueError("engagement evidence_ref required")
        if not str(self.observed_at or "").strip():
            raise ValueError("engagement observed_at required")


def choose_lead_magnet(
    *,
    config: NicheConfig,
    intent_class: str | None,
    event_signal_observed: bool,
) -> str | None:
    config.validate()
    intent = str(intent_class or "").strip().lower()
    for key in config.preferred_lead_magnets:
        spec = LEAD_MAGNETS[key]
        if intent not in spec["intent_classes"]:
            continue
        if spec["requires_event_signal"] and not event_signal_observed:
            continue
        return key
    return None


def build_gtm_plan(
    config: NicheConfig,
    lead: GtmLeadEvidence,
) -> dict[str, Any]:
    config.validate()
    lead.validate()

    blockers: list[str] = []
    refs = tuple(
        dict.fromkeys(
            [
                *lead.intent_evidence_refs,
                *(
                    (lead.score_evidence_ref,)
                    if str(lead.score_evidence_ref or "").strip()
                    else ()
                ),
            ]
        )
    )

    if niche_family(lead.niche) != niche_family(config.niche):
        blockers.append("niche_mismatch")
    if (
        config.target_metros
        and str(lead.metro or "").strip().lower()
        not in {m.strip().lower() for m in config.target_metros}
    ):
        blockers.append("outside_target_metro")
    if lead.score is None:
        blockers.append("qualification_score_unknown")
    elif int(lead.score) < config.score_threshold:
        blockers.append("below_niche_score_threshold")
    if not str(lead.score_evidence_ref or "").strip():
        blockers.append("qualification_score_evidence_missing")
    if not lead.contact_ready:
        blockers.append("contact_not_ready")
    if not lead.outreach_ready:
        blockers.append("outreach_not_ready")
    if not refs:
        blockers.append("gtm_evidence_missing")

    magnet = choose_lead_magnet(
        config=config,
        intent_class=lead.intent_class,
        event_signal_observed=lead.event_signal_observed,
    )

    eligible = not blockers
    return {
        "schema_version": "empire.gtm_swarm.v6",
        "prospect_id": lead.prospect_id,
        "niche": niche_family(config.niche),
        "metro": lead.metro,
        "score_threshold": config.score_threshold,
        "observed_score": lead.score,
        "eligible_for_copy_draft": eligible,
        "eligible_for_governed_outbound_handoff": eligible,
        "blockers": sorted(set(blockers)),
        "lead_magnet_key": magnet,
        "lead_magnet": LEAD_MAGNETS.get(magnet) if magnet else None,
        "copy_generation": {
            "mode": "draft_only",
            "model_policy": "local_or_governed_model_router",
            "variant_count": 3,
            "automatic_winner_selection": False,
        },
        "execution": {
            "direct_send": False,
            "handoff": "canonical_gtm_outbound_governor",
            "standing_authority_required": True,
            "suppression_check_required": True,
            "daily_cap_required": True,
        },
        "evidence_refs": list(refs),
        "actual_revenue": False,
    }


def rescore_engagement(
    *,
    base_score: int,
    events: Iterable[EngagementEvent],
) -> dict[str, Any]:
    if not 0 <= int(base_score) <= 100:
        raise ValueError("base_score must be 0-100")

    delta = 0
    refs: list[str] = []
    terminal_stop = False
    event_rows: list[dict[str, Any]] = []

    for event in events:
        event.validate()
        weight = ENGAGEMENT_WEIGHTS[event.event_type]
        delta += weight
        refs.append(event.evidence_ref)
        if event.event_type in {"unsubscribe", "bounce"}:
            terminal_stop = True
        event_rows.append(
            {
                **asdict(event),
                "weight": weight,
            }
        )

    score = max(0, min(100, int(base_score) + delta))
    if terminal_stop:
        score = 0

    return {
        "schema_version": "empire.gtm_engagement_rescore.v1",
        "base_score": int(base_score),
        "score_delta": delta,
        "rescored": score,
        "terminal_stop": terminal_stop,
        "events": event_rows,
        "evidence_refs": list(dict.fromkeys(refs)),
        "reengagement_eligible": bool(refs) and not terminal_stop,
        "direct_send": False,
        "handoff": "canonical_gtm_outbound_governor",
        "actual_revenue": False,
    }


def niche_config_from_mapping(raw: Mapping[str, Any]) -> NicheConfig:
    return NicheConfig(
        niche=str(raw.get("niche") or "").strip(),
        icp_key=str(raw.get("icp_key") or "").strip(),
        target_metros=tuple(
            str(value).strip()
            for value in raw.get("target_metros", ())
            if str(value).strip()
        ),
        score_threshold=int(raw.get("score_threshold", 70)),
        allowed_channels=tuple(
            str(value).strip().lower()
            for value in raw.get("allowed_channels", ("email",))
            if str(value).strip()
        ),
        preferred_lead_magnets=tuple(
            str(value).strip()
            for value in raw.get(
                "preferred_lead_magnets",
                tuple(LEAD_MAGNETS),
            )
            if str(value).strip()
        ),
    )
