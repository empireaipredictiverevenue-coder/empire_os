"""Phase 9 evidence-only ad-to-landing-page feedback review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.advertising_review import CampaignEconomicsReview


@dataclass(frozen=True)
class LandingPageOutcomeEvidence:
    campaign_id: str
    landing_page_id: str
    evidence_ref: str | None
    sessions: int | None
    qualified_actions: int | None

    def validate(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("campaign_id required")
        if not self.landing_page_id.strip():
            raise ValueError("landing_page_id required")
        if self.sessions is not None and self.sessions < 0:
            raise ValueError("sessions must be nonnegative")
        if self.qualified_actions is not None and self.qualified_actions < 0:
            raise ValueError("qualified_actions must be nonnegative")
        if (
            self.sessions is not None
            and self.qualified_actions is not None
            and self.qualified_actions > self.sessions
        ):
            raise ValueError("qualified_actions cannot exceed sessions")


@dataclass(frozen=True)
class AdvertisingLandingFeedbackReview:
    campaign_id: str
    landing_page_id: str
    review_ready: bool
    landing_conversion_rate: float | None
    campaign_roas: float | None
    campaign_profit_roas: float | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    campaign_creation: bool = False
    budget_mutation: bool = False
    pause_mutation: bool = False
    retarget_execution: bool = False
    landing_page_mutation: bool = False
    publishing_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_landing_page_feedback(
    *,
    campaign: CampaignEconomicsReview,
    landing: LandingPageOutcomeEvidence,
) -> AdvertisingLandingFeedbackReview:
    landing.validate()
    if campaign.campaign_id != landing.campaign_id:
        raise ValueError("campaign/landing evidence mismatch")

    blockers = list(campaign.blockers)
    refs: list[str] = []
    landing_ref = str(landing.evidence_ref or "").strip()
    if landing_ref:
        refs.append(landing_ref)
    else:
        blockers.append("landing_page_evidence_missing")

    if landing.sessions is None:
        blockers.append("landing_sessions_unknown")
    if landing.qualified_actions is None:
        blockers.append("landing_qualified_actions_unknown")

    conversion_rate = None
    if (
        landing.sessions is not None
        and landing.qualified_actions is not None
        and landing.sessions > 0
    ):
        conversion_rate = landing.qualified_actions / landing.sessions
    elif landing.sessions == 0 and landing.qualified_actions == 0:
        conversion_rate = None
        blockers.append("landing_conversion_rate_unavailable_without_sessions")

    if not campaign.attribution_complete:
        blockers.append("campaign_attribution_incomplete")

    ordered = tuple(sorted(set(blockers)))
    return AdvertisingLandingFeedbackReview(
        campaign_id=campaign.campaign_id,
        landing_page_id=landing.landing_page_id,
        review_ready=not ordered,
        landing_conversion_rate=(
            round(conversion_rate, 4)
            if conversion_rate is not None
            else None
        ),
        campaign_roas=campaign.roas,
        campaign_profit_roas=campaign.profit_roas,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
