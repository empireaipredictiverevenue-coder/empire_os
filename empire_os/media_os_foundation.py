"""Empire Media OS Phase A foundation.

Media OS is an extension of the existing Marketing & Growth department and
Predictive Cloud attention layer. It does not own a parallel evidence store,
model registry, opportunity engine, analytics truth system, revenue ledger, or
execution authority.

Phase A is intentionally internal/draft-only:
- evidence-linked research/content objects may be created;
- media opportunity feature packets may be prepared for existing Quant/
  Opportunity systems;
- public publishing, new-channel creation, sponsor/collaboration outreach,
  and material GPU/cloud commitments remain governed gates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


MEDIA_OS_MODE = "OBSERVE"
MEDIA_OS_DEPARTMENT = "marketing_growth"
MEDIA_OS_COMPONENT = "media_os"

SUBSCRIBER_MILESTONES = (
    1_000,
    5_000,
    10_000,
    25_000,
    50_000,
    100_000,
    250_000,
    500_000,
    1_000_000,
)

MIN_CHANNEL_LAUNCH_IDEAS = 30
CHANNEL_LAUNCH_IDEA_TARGET_HIGH = 50


SOURCE_ADAPTERS: tuple[dict[str, Any], ...] = (
    {
        "source": "astra_executive",
        "classification": "REUSE",
        "purpose": "coordination, prioritisation and founder gates",
    },
    {
        "source": "intelligence_fabric",
        "classification": "REUSE_ENHANCE",
        "purpose": "shared graph, provenance and temporal evidence",
    },
    {
        "source": "quant_brain",
        "classification": "REUSE",
        "purpose": "economics, uncertainty, VOI and portfolio ranking",
    },
    {
        "source": "opportunity_factory",
        "classification": "REUSE",
        "purpose": "commercial opportunity lifecycle",
    },
    {
        "source": "market_sweeps",
        "classification": "REUSE",
        "purpose": "market and territory evidence",
    },
    {
        "source": "revenue_pulse",
        "classification": "REUSE",
        "purpose": "recognized revenue and realized GP truth",
    },
    {
        "source": "search_intelligence",
        "classification": "REUSE_ENHANCE",
        "purpose": "search, AEO, GEO and content opportunity evidence",
    },
    {
        "source": "competitor_audience_intelligence",
        "classification": "REUSE_ENHANCE",
        "purpose": "public competitor and audience evidence",
    },
    {
        "source": "community_intent",
        "classification": "REUSE_ENHANCE",
        "purpose": "public community pain and language",
    },
    {
        "source": "conversation_os",
        "classification": "REUSE_ENHANCE",
        "purpose": "voice-of-buyer and conversation evidence",
    },
    {
        "source": "revenue_crm",
        "classification": "REUSE_ENHANCE",
        "purpose": "lead, opportunity and customer journey evidence",
    },
    {
        "source": "voice_lab",
        "classification": "REUSE_ENHANCE",
        "purpose": "self-hosted speech and narration foundation",
    },
    {
        "source": "model_registry",
        "classification": "ENHANCE",
        "purpose": "model/provider policy, cost, quality and licence metadata",
    },
    {
        "source": "experiment_intelligence",
        "classification": "REUSE_ENHANCE",
        "purpose": "controlled experiment truth and causal review",
    },
    {
        "source": "founder_console",
        "classification": "REUSE_ENHANCE",
        "purpose": "canonical executive media status surface",
    },
)


@dataclass(frozen=True)
class MediaClaim:
    """A factual or interpretive content claim with source lineage."""

    claim: str
    claim_type: str = "factual"
    evidence_refs: tuple[str, ...] = ()
    source_timestamp: str | None = None
    freshness_class: str = "UNKNOWN"
    uncertainty: str | None = None

    def validate(self) -> None:
        if not self.claim.strip():
            raise ValueError("media claim text is required")
        allowed = {"factual", "interpretive", "opinion", "hypothesis"}
        if self.claim_type not in allowed:
            raise ValueError("unsupported media claim type")
        if self.claim_type == "factual" and not self.evidence_refs:
            raise ValueError(
                "factual media claims require evidence_refs"
            )

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class CanonicalContentObject:
    """Single evidence-linked source object for cross-platform derivatives."""

    content_id: str
    topic: str
    thesis: str
    audience: str
    claims: tuple[MediaClaim, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    insight_refs: tuple[str, ...] = ()
    opportunity_refs: tuple[str, ...] = ()
    product_refs: tuple[str, ...] = ()
    stories: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    visual_ideas: tuple[str, ...] = ()
    cta: str | None = None
    uncertainty: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.content_id.strip():
            raise ValueError("content_id is required")
        if not self.topic.strip():
            raise ValueError("topic is required")
        if not self.thesis.strip():
            raise ValueError("thesis is required")
        if not self.audience.strip():
            raise ValueError("audience is required")

        for claim in self.claims:
            claim.validate()

        claim_refs = {
            ref
            for claim in self.claims
            for ref in claim.evidence_refs
        }
        if self.claims and not (set(self.evidence_refs) | claim_refs):
            raise ValueError(
                "content with claims requires canonical evidence references"
            )

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["claims"] = [claim.as_dict() for claim in self.claims]
        result.update({
            "schema_version": "empire.media.canonical_content.v1",
            "mode": MEDIA_OS_MODE,
            "public_publish_authorized": False,
            "actual_revenue": False,
            "execution_authority": "none",
        })
        return result


def _bounded(value: Any) -> float | None:
    """Normalize an observed feature to 0..1 without inventing missing data."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, number))


def build_media_opportunity_feature_packet(
    *,
    topic: str,
    evidence_refs: Iterable[str],
    features: Mapping[str, Any],
    source_systems: Iterable[str] = (),
) -> dict[str, Any]:
    """Prepare media features for existing Quant/Opportunity ranking.

    Media OS deliberately does not turn this packet into revenue, demand,
    purchase intent, or a guaranteed growth forecast.
    """
    refs = tuple(
        str(ref).strip()
        for ref in evidence_refs
        if str(ref).strip()
    )
    if not str(topic or "").strip():
        raise ValueError("media opportunity topic is required")
    if not refs:
        raise ValueError("media opportunity evidence_refs are required")

    allowed = (
        "audience_demand",
        "content_supply_gap",
        "trend_velocity",
        "empire_expertise",
        "content_depth",
        "monetisation_potential",
        "buyer_density",
        "advertiser_value",
        "search_potential",
        "youtube_outlier_evidence",
        "product_alignment",
        "competitive_differentiation",
        "production_feasibility",
        "originality",
        "audience_fit",
        "recommendation_potential",
        "strategic_relevance",
    )
    observed = {
        key: _bounded(features.get(key))
        for key in allowed
    }

    return {
        "schema_version": "empire.media.opportunity_features.v1",
        "mode": MEDIA_OS_MODE,
        "topic": str(topic).strip(),
        "features": observed,
        "known_feature_count": sum(
            value is not None for value in observed.values()
        ),
        "evidence_refs": list(refs),
        "source_systems": sorted({
            str(value).strip()
            for value in source_systems
            if str(value).strip()
        }),
        "ranking_owner": "quant_brain_and_opportunity_factory",
        "media_opportunity_score": None,
        "score_created": False,
        "buyer_intent_inferred": False,
        "revenue_inferred": False,
        "subscriber_forecast_created": False,
        "execution_authority": "none",
    }


def evaluate_channel_launch_candidate(
    *,
    channel_concept: str,
    credible_idea_count: int,
    evidence_refs: Iterable[str],
    content_depth_confirmed: bool,
    market_evidence_confirmed: bool,
) -> dict[str, Any]:
    """Evaluate launch readiness without creating or launching a channel."""
    refs = [
        str(value).strip()
        for value in evidence_refs
        if str(value).strip()
    ]
    idea_count = max(0, int(credible_idea_count))
    depth_ok = bool(content_depth_confirmed)
    evidence_ok = bool(market_evidence_confirmed and refs)
    minimum_met = idea_count >= MIN_CHANNEL_LAUNCH_IDEAS

    if not minimum_met or not depth_ok or not evidence_ok:
        decision = "HOLD"
    else:
        decision = "FOUNDER_REVIEW_CANDIDATE"

    return {
        "schema_version": "empire.media.channel_launch_candidate.v1",
        "mode": MEDIA_OS_MODE,
        "channel_concept": str(channel_concept or "").strip(),
        "credible_idea_count": idea_count,
        "credible_idea_target_range": [
            MIN_CHANNEL_LAUNCH_IDEAS,
            CHANNEL_LAUNCH_IDEA_TARGET_HIGH,
        ],
        "content_depth_confirmed": depth_ok,
        "market_evidence_confirmed": bool(market_evidence_confirmed),
        "evidence_refs": refs,
        "decision": decision,
        "channel_created": False,
        "channel_launch_authorized": False,
        "founder_gate_required": decision == "FOUNDER_REVIEW_CANDIDATE",
        "execution_authority": (
            "founder_gate"
            if decision == "FOUNDER_REVIEW_CANDIDATE"
            else "none"
        ),
    }


def media_os_architecture_contract() -> dict[str, Any]:
    """Canonical Phase A Media OS integration contract."""
    return {
        "schema_version": "empire.media_os.foundation.v1",
        "phase": "A",
        "mode": MEDIA_OS_MODE,
        "department": MEDIA_OS_DEPARTMENT,
        "component": MEDIA_OS_COMPONENT,
        "mission": (
            "convert Empire evidence, builds and market intelligence into "
            "premium governed media and return audience learning to EmpireOS"
        ),
        "source_adapters": [dict(row) for row in SOURCE_ADAPTERS],
        "shared_system_rules": {
            "evidence_store": "intelligence_fabric",
            "commercial_opportunity": "opportunity_factory",
            "ranking_and_economics": "quant_brain",
            "revenue_truth": "revenue_pulse",
            "search_truth": "search_intelligence",
            "model_selection": "model_registry_and_intelligence_router",
            "experiments": "experiment_intelligence",
            "customer_truth": "revenue_crm",
            "executive_surface": "founder_console",
        },
        "new_media_contracts": [
            "canonical_content_object",
            "media_opportunity_feature_packet",
            "youtube_intelligence_adapter",
            "algorithm_intelligence_engine",
            "media_trend_fusion",
            "media_research_pack",
            "video_idea_factory",
            "evidence_constrained_script_brief",
            "title_thumbnail_creative_package",
            "storyboard_and_shot_list",
            "ai_video_timeline",
            "rights_and_provenance_manifest",
            "media_quality_gate",
            "render_plan_and_cost_governor",
            "publishing_calendar",
            "governed_publish_package",
            "owned_channel_analytics",
            "retention_intelligence",
            "media_experiment_packet",
            "attention_graph_packet",
            "media_attribution_packet",
            "comment_intelligence",
            "build_journal",
            "canonical_repurposing",
            "duplication_guard",
            "content_refresh_and_decay",
            "channel_spawning_candidate",
            "workflow_skill_candidate_compiler",
            "flagship_media_runtime",
            "empire_intelligence_bridge",
        ],
        "subscriber_strategy": {
            "first_major_scale_milestone": 100_000,
            "long_term_network_objective": 1_000_000,
            "milestones": list(SUBSCRIBER_MILESTONES),
            "guaranteed": False,
            "fixed_date_forecast": False,
        },
        "quality_policy": {
            "cheap_faceless_content_farm": False,
            "evidence_required_for_factual_claims": True,
            "originality_required": True,
            "rights_required": True,
            "synthetic_events_must_not_be_presented_as_real": True,
            "quality_over_volume": True,
        },
        "authority": {
            "internal_research_generation_testing": "internal_write",
            "public_publish_authorized": False,
            "comment_publish_authorized": False,
            "new_channel_launch_authorized": False,
            "material_gpu_cloud_commitment_authorized": False,
            "sponsor_outbound_authorized": False,
            "creator_outreach_authorized": False,
            "binding_media_contract_authorized": False,
            "founder_gate_actions": [
                "new_public_channel",
                "material_gpu_or_cloud_commitment",
                "major_brand_change",
                "significant_external_authority",
                "binding_sponsor_or_commercial_contract",
                "irreversible_spend",
                "legally_sensitive_content_decision",
            ],
        },
        "publishing_state": "DRAFT_ONLY",
        "runtime_active": False,
        "actual_revenue": False,
        "recognized_revenue_cents": None,
        "execution_authority": "none",
    }


def media_os_founder_status(
    runtime_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = media_os_architecture_contract()
    runtime = (
        dict(runtime_payload)
        if isinstance(runtime_payload, Mapping)
        else {}
    )
    youtube = (
        runtime.get("youtube_public")
        if isinstance(runtime.get("youtube_public"), Mapping)
        else {}
    )
    outliers = (
        youtube.get("outliers")
        if isinstance(youtube.get("outliers"), Mapping)
        else {}
    )
    owned = (
        runtime.get("owned_video_metrics")
        if isinstance(runtime.get("owned_video_metrics"), Mapping)
        else {}
    )
    owned_totals = (
        owned.get("observed_totals")
        if isinstance(owned.get("observed_totals"), Mapping)
        else {}
    )
    algorithm = (
        runtime.get("algorithm_intelligence")
        if isinstance(runtime.get("algorithm_intelligence"), Mapping)
        else {}
    )
    trends = (
        runtime.get("trend_fusion")
        if isinstance(runtime.get("trend_fusion"), Mapping)
        else {}
    )
    journal = (
        runtime.get("build_journal")
        if isinstance(runtime.get("build_journal"), Mapping)
        else {}
    )
    ideas = (
        runtime.get("idea_backlog")
        if isinstance(runtime.get("idea_backlog"), Mapping)
        else {}
    )

    return {
        "architecture_available": True,
        "runtime_active": runtime.get("runtime_active") is True,
        "runtime_generated_at": runtime.get("generated_at"),
        "real_evidence_present": runtime.get("real_evidence_present") is True,
        "observed_source_count": int(
            runtime.get("observed_source_count") or 0
        ),
        "phase": contract["phase"],
        "mode": contract["mode"],
        "department": contract["department"],
        "publishing_state": contract["publishing_state"],
        "source_adapter_count": len(contract["source_adapters"]),
        "media_contract_count": len(contract["new_media_contracts"]),
        "algorithm_intelligence_available": (
            "algorithm_intelligence_engine"
            in contract["new_media_contracts"]
        ),
        "youtube_observation_count": int(
            youtube.get("observation_count") or 0
        ),
        "outlier_candidate_count": int(
            outliers.get("candidate_count") or 0
        ),
        "owned_video_metric_count": int(
            owned.get("record_count") or 0
        ),
        "owned_views_observed": owned_totals.get("views"),
        "owned_engaged_views_observed": owned_totals.get(
            "engaged_views"
        ),
        "owned_watch_time_minutes_observed": owned_totals.get(
            "watch_time_minutes"
        ),
        "owned_subscribers_gained_observed": owned_totals.get(
            "subscribers_gained"
        ),
        "owned_subscribers_lost_observed": owned_totals.get(
            "subscribers_lost"
        ),
        "algorithm_observation_count": int(
            algorithm.get("observation_count") or 0
        ),
        "algorithm_hypothesis_count": int(
            algorithm.get("hypothesis_count") or 0
        ),
        "trend_topic_count": int(trends.get("topic_count") or 0),
        "build_journal_opportunity_count": int(
            journal.get("opportunity_candidate_count") or 0
        ),
        "idea_candidate_count": int(
            ideas.get("candidate_count") or 0
        ),
        "pending_quant_review_count": int(
            ideas.get("pending_quant_review_count") or 0
        ),
        "commercial_quant_available_count": int(
            ideas.get("commercial_quant_available_count") or 0
        ),
        "ready_for_research_generation": (
            runtime.get("ready_for_research_generation") is True
        ),
        "first_major_scale_milestone": 100_000,
        "long_term_network_objective": 1_000_000,
        "subscriber_targets_are_guarantees": False,
        "public_publish_authorized": False,
        "new_channel_launch_authorized": False,
        "material_gpu_cloud_commitment_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
