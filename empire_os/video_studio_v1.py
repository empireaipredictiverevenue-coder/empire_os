"""Empire AI evidence-first video studio planning.

Hybrid model:
- real browser/app captures remain the proof layer;
- AI generation may add motion, transitions, narration and social cuts;
- synthetic scenes must never be presented as observed commercial proof.

This module plans assets only. It does not record, generate, publish, or
distribute media.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


ALLOWED_SCENE_TYPES = {
    "live_capture",
    "screenshot_motion",
    "data_visualization",
    "ai_broll",
    "title_card",
    "cta",
}

ALLOWED_OUTPUTS = {
    "sales_demo",
    "pre_nurture",
    "social_cut",
    "case_study",
    "tutorial",
}


@dataclass(frozen=True)
class VideoScene:
    scene_type: str
    purpose: str
    evidence_ref: str | None
    prompt: str | None = None
    source_asset_ref: str | None = None
    duration_seconds: int = 8

    def validate(self) -> None:
        if self.scene_type not in ALLOWED_SCENE_TYPES:
            raise ValueError(f"unsupported scene_type: {self.scene_type}")
        if not str(self.purpose or "").strip():
            raise ValueError("scene purpose required")
        if not 2 <= int(self.duration_seconds) <= 60:
            raise ValueError("scene duration must be 2-60 seconds")

        proof_scene = self.scene_type in {
            "live_capture",
            "screenshot_motion",
            "data_visualization",
        }
        if proof_scene and not str(self.evidence_ref or "").strip():
            raise ValueError(
                "proof scenes require evidence_ref"
            )
        if self.scene_type == "screenshot_motion" and not str(
            self.source_asset_ref or ""
        ).strip():
            raise ValueError(
                "screenshot_motion requires source_asset_ref"
            )
        if self.scene_type == "ai_broll" and not str(
            self.prompt or ""
        ).strip():
            raise ValueError("ai_broll requires prompt")


def build_video_studio_plan(
    *,
    title: str,
    niche: str,
    output_type: str,
    scenes: Iterable[VideoScene],
    voice_style: str = "founder_direct",
    aspect_ratios: tuple[str, ...] = ("16:9", "9:16", "1:1"),
) -> dict[str, Any]:
    if not str(title or "").strip():
        raise ValueError("title required")
    if not str(niche or "").strip():
        raise ValueError("niche required")
    if output_type not in ALLOWED_OUTPUTS:
        raise ValueError(f"unsupported output_type: {output_type}")

    rows = tuple(scenes)
    if not rows:
        raise ValueError("at least one scene required")
    for row in rows:
        row.validate()

    proof_refs = tuple(
        dict.fromkeys(
            str(row.evidence_ref).strip()
            for row in rows
            if str(row.evidence_ref or "").strip()
        )
    )
    source_refs = tuple(
        dict.fromkeys(
            str(row.source_asset_ref).strip()
            for row in rows
            if str(row.source_asset_ref or "").strip()
        )
    )
    total_duration = sum(int(row.duration_seconds) for row in rows)

    return {
        "schema_version": "empire.video_studio.v1",
        "title": title.strip(),
        "niche": niche.strip(),
        "output_type": output_type,
        "scenes": [asdict(row) for row in rows],
        "target_duration_seconds": total_duration,
        "voice": {
            "style": voice_style,
            "provider": "governed_voice_adapter",
            "enabled": False,
        },
        "generation": {
            "browser_capture_adapter": "playwright_optional",
            "motion_generation_adapter": "local_or_governed_video_model",
            "ffmpeg_compositor": "optional",
            "captions": True,
            "chaptering": True,
            "cta_generation": True,
            "auto_title": True,
            "auto_summary": True,
            "social_cuts": output_type != "social_cut",
        },
        "aspect_ratios": list(aspect_ratios),
        "proof_evidence_refs": list(proof_refs),
        "source_asset_refs": list(source_refs),
        "truth_policy": {
            "live_capture_is_proof": True,
            "generated_broll_is_proof": False,
            "generated_motion_is_observed_revenue_evidence": False,
            "synthetic_metrics_allowed": False,
            "pricing_claims_require_verified_evidence": True,
            "revenue_claims_require_revenue_truth": True,
        },
        "telemetry": {
            "viewer_start": True,
            "viewer_25": True,
            "viewer_50": True,
            "viewer_75": True,
            "viewer_complete": True,
            "cta_click": True,
            "reply_attribution": True,
            "conversion_intelligence_handoff": True,
        },
        "recording_enabled": False,
        "generation_enabled": False,
        "publishing_enabled": False,
        "automatic_distribution": False,
        "actual_revenue": False,
    }
