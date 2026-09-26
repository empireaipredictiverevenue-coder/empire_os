"""Provider-agnostic render planning and queue policy for Media OS.

Phase A/G foundation only: plans jobs and preserves cost/licence requirements.
It does not execute FFmpeg, provision GPUs, or spend cloud budget.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


RENDER_PRIORITIES = {
    "P0": "breaking_content",
    "P1": "flagship",
    "P2": "niche_long_form",
    "P3": "shorts",
    "P4": "experiments",
}

RENDER_PROVIDERS = {
    "ffmpeg": {
        "type": "local_process",
        "open_source_first": True,
        "licence_profile_required": True,
    },
    "internal_motion": {
        "type": "code_defined_motion",
        "open_source_first": True,
        "licence_profile_required": False,
    },
    "react_renderer": {
        "type": "optional_adapter",
        "open_source_first": False,
        "licence_profile_required": True,
    },
    "licensed_adapter": {
        "type": "optional_commercial_adapter",
        "open_source_first": False,
        "licence_profile_required": True,
    },
}


@dataclass(frozen=True)
class MediaRenderJob:
    job_id: str
    production_id: str
    timeline_ref: str
    output_profile: str
    priority: str
    renderer: str = "ffmpeg"
    asset_manifest_ref: str | None = None
    rights_manifest_ref: str | None = None
    qc_policy_ref: str | None = None
    estimated_gpu_minutes: float | None = None
    estimated_cost_usd: float | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.job_id.strip():
            raise ValueError("render job_id is required")
        if not self.production_id.strip():
            raise ValueError("render production_id is required")
        if not self.timeline_ref.strip():
            raise ValueError("render timeline_ref is required")
        if self.priority not in RENDER_PRIORITIES:
            raise ValueError("unsupported render priority")
        if self.renderer not in RENDER_PROVIDERS:
            raise ValueError("unsupported renderer")
        if self.estimated_gpu_minutes is not None:
            if float(self.estimated_gpu_minutes) < 0:
                raise ValueError("estimated_gpu_minutes cannot be negative")
        if self.estimated_cost_usd is not None:
            if float(self.estimated_cost_usd) < 0:
                raise ValueError("estimated_cost_usd cannot be negative")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_render_plan(
    job: MediaRenderJob,
    *,
    renderer_license_ref: str | None = None,
    ffmpeg_build_ref: str | None = None,
    codec_policy_ref: str | None = None,
    material_spend_threshold_usd: float = 50.0,
) -> dict[str, Any]:
    job.validate()
    provider = dict(RENDER_PROVIDERS[job.renderer])

    licence_ready = True
    if job.renderer == "ffmpeg":
        licence_ready = bool(
            str(ffmpeg_build_ref or "").strip()
            and str(codec_policy_ref or "").strip()
        )
    elif provider["licence_profile_required"]:
        licence_ready = bool(
            str(renderer_license_ref or "").strip()
        )

    cost = (
        float(job.estimated_cost_usd)
        if job.estimated_cost_usd is not None
        else None
    )
    material_spend = (
        cost is not None
        and cost >= max(0.0, float(material_spend_threshold_usd))
    )

    if not licence_ready:
        state = "BLOCKED_LICENSE_PROFILE"
    elif cost is None:
        state = "HOLD_COST_UNKNOWN"
    elif material_spend:
        state = "FOUNDER_GATE_MATERIAL_SPEND"
    else:
        state = "INTERNAL_RENDER_CANDIDATE"

    return {
        "schema_version": "empire.media.render_plan.v1",
        "mode": "OBSERVE",
        "job": job.as_dict(),
        "provider": provider,
        "priority_label": RENDER_PRIORITIES[job.priority],
        "renderer_license_ref": renderer_license_ref,
        "ffmpeg_build_ref": ffmpeg_build_ref,
        "codec_policy_ref": codec_policy_ref,
        "licence_ready": licence_ready,
        "cost_known": cost is not None,
        "material_spend": material_spend,
        "state": state,
        "render_executed": False,
        "gpu_provisioned": False,
        "cloud_spend_committed": False,
        "founder_gate_required": state == "FOUNDER_GATE_MATERIAL_SPEND",
        "execution_authority": (
            "founder_gate"
            if state == "FOUNDER_GATE_MATERIAL_SPEND"
            else "none"
        ),
    }


def queue_policy() -> dict[str, Any]:
    return {
        "schema_version": "empire.media.render_queue_policy.v1",
        "priorities": dict(RENDER_PRIORITIES),
        "features": [
            "bounded_concurrency",
            "retry_budget",
            "job_state",
            "asset_cache",
            "resume_checkpoint",
            "failed_render_recovery",
            "cost_tracking",
            "gpu_utilisation",
            "scheduling",
        ],
        "live_queue_enabled": False,
        "automatic_gpu_provisioning": False,
        "material_spend_authorized": False,
        "execution_authority": "none",
    }


def cost_governor(
    *,
    opportunity_score: float | None,
    expected_cost_usd: float | None,
    expected_gpu_minutes: float | None,
    premium_generation_requested: bool,
) -> dict[str, Any]:
    score = None
    if opportunity_score is not None:
        score = max(0.0, min(1.0, float(opportunity_score)))
    cost = (
        max(0.0, float(expected_cost_usd))
        if expected_cost_usd is not None
        else None
    )
    gpu = (
        max(0.0, float(expected_gpu_minutes))
        if expected_gpu_minutes is not None
        else None
    )

    if score is None or cost is None:
        route = "HOLD_UNKNOWN_ECONOMICS"
    elif premium_generation_requested and score >= 0.75:
        route = "PREMIUM_GENERATION_CANDIDATE"
    elif score >= 0.45:
        route = "STANDARD_GENERATION_CANDIDATE"
    else:
        route = "LOW_COST_EXPERIMENT_OR_HOLD"

    return {
        "schema_version": "empire.media.cost_governor.v1",
        "opportunity_score": score,
        "expected_cost_usd": cost,
        "expected_gpu_minutes": gpu,
        "premium_generation_requested": premium_generation_requested,
        "route": route,
        "automatic_spend_authorized": False,
        "actual_cost_usd": None,
        "actual_revenue": False,
        "execution_authority": "none",
    }
