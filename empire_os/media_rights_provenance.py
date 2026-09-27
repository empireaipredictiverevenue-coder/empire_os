"""Rights and provenance contracts for Empire Media OS assets."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


ALLOWED_RIGHTS_STATES = frozenset({
    "OWNED",
    "LICENSED_COMMERCIAL",
    "PUBLIC_DOMAIN",
    "ATTRIBUTION_LICENSE",
    "UNKNOWN",
    "RESTRICTED",
})


@dataclass(frozen=True)
class MediaAssetProvenance:
    asset_id: str
    asset_type: str
    source_type: str
    source_ref: str
    creator_or_provider: str | None = None
    license_id: str | None = None
    rights_state: str = "UNKNOWN"
    attribution_required: bool | None = None
    attribution_text: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    workflow_version: str | None = None
    generated_at: str | None = None
    obtained_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id is required")
        if not self.asset_type.strip():
            raise ValueError("asset_type is required")
        if not self.source_type.strip() or not self.source_ref.strip():
            raise ValueError("asset source_type/source_ref are required")
        if self.rights_state not in ALLOWED_RIGHTS_STATES:
            raise ValueError("unsupported rights_state")

    def commercial_use_eligible(self) -> bool:
        self.validate()
        if self.rights_state not in {
            "OWNED",
            "LICENSED_COMMERCIAL",
            "PUBLIC_DOMAIN",
            "ATTRIBUTION_LICENSE",
        }:
            return False
        if self.rights_state == "ATTRIBUTION_LICENSE":
            return (
                self.attribution_required is True
                and bool(str(self.attribution_text or "").strip())
            )
        return True

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "commercial_use_eligible": self.commercial_use_eligible(),
        }


def build_rights_manifest(
    *,
    production_id: str,
    assets: list[MediaAssetProvenance],
) -> dict[str, Any]:
    if not str(production_id or "").strip():
        raise ValueError("production_id is required")
    rows = [asset.as_dict() for asset in assets]
    blocked = [
        row["asset_id"]
        for row in rows
        if not row["commercial_use_eligible"]
    ]
    attributions = [
        {
            "asset_id": row["asset_id"],
            "text": row["attribution_text"],
        }
        for row in rows
        if row["attribution_required"] is True
        and row.get("attribution_text")
    ]
    return {
        "schema_version": "empire.media.rights_manifest.v1",
        "production_id": production_id,
        "asset_count": len(rows),
        "assets": rows,
        "blocked_asset_ids": blocked,
        "required_attributions": attributions,
        "commercial_release_ready": not blocked and bool(rows),
        "rights_unknown_hidden": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def synthetic_media_disclosure(
    *,
    synthetic_person: bool = False,
    altered_real_footage: bool = False,
    synthetic_event_or_place: bool = False,
    reenactment: bool = False,
) -> dict[str, Any]:
    disclosure_required = any((
        synthetic_person,
        altered_real_footage,
        synthetic_event_or_place,
        reenactment,
    ))
    return {
        "schema_version": "empire.media.synthetic_disclosure.v1",
        "synthetic_person": bool(synthetic_person),
        "altered_real_footage": bool(altered_real_footage),
        "synthetic_event_or_place": bool(synthetic_event_or_place),
        "reenactment": bool(reenactment),
        "platform_disclosure_review_required": disclosure_required,
        "present_as_unaltered_real_event_authorized": False,
        "execution_authority": "none",
    }
