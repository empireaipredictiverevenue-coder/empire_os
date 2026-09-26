"""Publishing package and calendar contracts for Empire Media OS.

This module prepares deterministic publish-ready artifacts and schedules.
It never performs a public publish action.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


CONTENT_TYPES = frozenset({
    "youtube_long_form",
    "youtube_short",
    "community_post",
    "linkedin",
    "x",
    "blog",
    "newsletter",
})

PRODUCTION_STATES = frozenset({
    "IDEA",
    "RESEARCH",
    "SCRIPT",
    "STORYBOARD",
    "ASSET_BUILD",
    "RENDER",
    "QC",
    "READY_FOR_GOVERNED_PUBLISH",
    "HOLD",
})


@dataclass(frozen=True)
class MediaCalendarItem:
    item_id: str
    channel_id: str
    content_type: str
    production_state: str
    priority: str
    topic_cluster: str
    content_ref: str
    publish_window_start: str | None = None
    publish_window_end: str | None = None
    campaign_ref: str | None = None
    experiment_ref: str | None = None
    dependency_refs: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.item_id.strip():
            raise ValueError("calendar item_id is required")
        if not self.channel_id.strip():
            raise ValueError("calendar channel_id is required")
        if self.content_type not in CONTENT_TYPES:
            raise ValueError("unsupported media content_type")
        if self.production_state not in PRODUCTION_STATES:
            raise ValueError("unsupported production_state")
        if not self.content_ref.strip():
            raise ValueError("calendar content_ref is required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_media_calendar(
    items: Iterable[MediaCalendarItem],
) -> dict[str, Any]:
    rows = [item.as_dict() for item in items]
    rows.sort(
        key=lambda row: (
            row.get("publish_window_start") is None,
            str(row.get("publish_window_start") or ""),
            str(row.get("priority") or ""),
            str(row.get("item_id") or ""),
        )
    )
    return {
        "schema_version": "empire.media.calendar.v1",
        "mode": "OBSERVE",
        "item_count": len(rows),
        "items": rows,
        "automatic_public_publish": False,
        "automatic_channel_creation": False,
        "execution_authority": "none",
    }


def prepare_publish_package(
    *,
    content_ref: str,
    rendered_asset_ref: str,
    thumbnail_ref: str,
    metadata_ref: str,
    rights_manifest: Mapping[str, Any],
    qc_gate: Mapping[str, Any],
    channel_id: str,
) -> dict[str, Any]:
    if not all(
        str(value or "").strip()
        for value in (
            content_ref,
            rendered_asset_ref,
            thumbnail_ref,
            metadata_ref,
            channel_id,
        )
    ):
        raise ValueError("publish package refs and channel_id are required")

    rights_ready = (
        rights_manifest.get("commercial_release_ready") is True
    )
    qc_ready = (
        qc_gate.get("publish_ready_candidate") is True
    )
    ready = rights_ready and qc_ready

    return {
        "schema_version": "empire.media.publish_package.v1",
        "mode": "OBSERVE",
        "channel_id": channel_id,
        "content_ref": content_ref,
        "rendered_asset_ref": rendered_asset_ref,
        "thumbnail_ref": thumbnail_ref,
        "metadata_ref": metadata_ref,
        "rights_manifest_ref": rights_manifest.get("production_id"),
        "rights_ready": rights_ready,
        "qc_ready": qc_ready,
        "state": (
            "READY_FOR_GOVERNED_PUBLISH_REVIEW"
            if ready
            else "HOLD"
        ),
        "publish_candidate_ready": ready,
        "public_publish_authorized": False,
        "publish_action_performed": False,
        "execution_authority": "none",
    }


def publishing_adapter_contract() -> dict[str, Any]:
    return {
        "schema_version": "empire.media.publisher_adapter.v1",
        "provider": "youtube",
        "supported_actions": [
            "prepare_upload",
            "prepare_schedule",
            "prepare_metadata_update",
            "prepare_thumbnail_update",
        ],
        "live_actions_enabled": False,
        "requires_authorized_channel": True,
        "requires_governed_publish_authority": True,
        "automatic_publish": False,
        "execution_authority": "none",
    }
