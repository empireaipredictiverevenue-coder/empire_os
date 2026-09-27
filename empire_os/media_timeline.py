"""Machine-readable storyboard and timeline contracts for Empire Media OS."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


EVIDENCE_VISUAL_TYPES = frozenset({
    "chart",
    "animated_data",
    "map",
    "comparison",
    "timeline",
    "architecture_diagram",
    "product_demo",
})


@dataclass(frozen=True)
class MediaShot:
    scene_id: str
    duration_seconds: float
    narration: str
    visual_intent: str
    asset_type: str
    animation: str | None = None
    camera: str | None = None
    caption: str | None = None
    data_refs: tuple[str, ...] = ()
    transition: str | None = None
    music_ref: str | None = None
    sfx_ref: str | None = None
    brand_overlay: str | None = None
    cta: str | None = None
    provenance_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.scene_id.strip():
            raise ValueError("scene_id is required")
        if float(self.duration_seconds) <= 0:
            raise ValueError("shot duration must be positive")
        if not self.visual_intent.strip():
            raise ValueError("visual_intent is required")
        if not self.asset_type.strip():
            raise ValueError("asset_type is required")
        if (
            self.asset_type in EVIDENCE_VISUAL_TYPES
            and not (self.data_refs or self.provenance_refs)
        ):
            raise ValueError(
                "evidence-derived visuals require data/provenance refs"
            )

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_media_timeline(
    *,
    video_id: str,
    shots: Iterable[MediaShot],
    script_ref: str,
    research_ref: str,
    brand_profile_ref: str,
) -> dict[str, Any]:
    if not str(video_id or "").strip():
        raise ValueError("video_id is required")
    if not str(script_ref or "").strip():
        raise ValueError("script_ref is required")
    if not str(research_ref or "").strip():
        raise ValueError("research_ref is required")

    rows = []
    cursor = 0.0
    for shot in shots:
        shot.validate()
        row = shot.as_dict()
        row["start_seconds"] = round(cursor, 3)
        cursor += float(shot.duration_seconds)
        row["end_seconds"] = round(cursor, 3)
        rows.append(row)

    if not rows:
        raise ValueError("timeline requires at least one shot")

    return {
        "schema_version": "empire.media.timeline.v1",
        "mode": "OBSERVE",
        "video_id": video_id,
        "script_ref": script_ref,
        "research_ref": research_ref,
        "brand_profile_ref": brand_profile_ref,
        "duration_seconds": round(cursor, 3),
        "shot_count": len(rows),
        "shots": rows,
        "deterministic_render_input": True,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def timeline_asset_plan(
    timeline: dict[str, Any],
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    for shot in timeline.get("shots") or []:
        assets.append({
            "scene_id": shot.get("scene_id"),
            "asset_type": shot.get("asset_type"),
            "visual_intent": shot.get("visual_intent"),
            "data_refs": list(shot.get("data_refs") or []),
            "provenance_refs": list(
                shot.get("provenance_refs") or []
            ),
            "rights_review_required": True,
        })

    return {
        "schema_version": "empire.media.asset_plan.v1",
        "video_id": timeline.get("video_id"),
        "asset_count": len(assets),
        "assets": assets,
        "generation_authorized": False,
        "rights_review_required": True,
        "execution_authority": "none",
    }
