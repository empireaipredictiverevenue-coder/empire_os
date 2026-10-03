"""Authority-free white-label projection for Digital Avatar workforces."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_avatar_clone_role_templates import (
    AvatarCloneRoleTemplate,
    clone_role_template_catalog,
)


@dataclass(frozen=True)
class AvatarWorkforceWhiteLabelConfig:
    tenant_id: str
    brand_name: str
    workforce_product_name: str
    allowed_template_keys: tuple[str, ...]
    brand_asset_ref: str | None = None

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("white-label workforce tenant_id required")
        if not self.brand_name.strip() or not self.workforce_product_name.strip():
            raise ValueError("white-label workforce brand/product name required")
        keys = tuple(
            str(value or "").strip().lower()
            for value in self.allowed_template_keys
        )
        if not keys or any(not value for value in keys):
            raise ValueError("white-label workforce template keys required")
        if len(keys) != len(set(keys)):
            raise ValueError("white-label workforce template keys must be unique")
        known = {item.key for item in clone_role_template_catalog()}
        unknown = tuple(sorted(set(keys) - known))
        if unknown:
            raise ValueError(
                "unknown white-label workforce template: "
                + ",".join(unknown)
            )
        if self.brand_asset_ref is not None and not str(
            self.brand_asset_ref
        ).strip():
            raise ValueError("brand_asset_ref must be non-empty when supplied")


@dataclass(frozen=True)
class AvatarWhiteLabelRoleProjection:
    template_key: str
    display_role: str
    branded_label: str
    capability_labels: tuple[str, ...]
    consultation_domains: tuple[str, ...]
    template_authority: str = "none"
    capability_override_allowed: bool = False
    consultation_override_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AvatarWhiteLabelWorkforceProjection:
    tenant_id: str
    brand_name: str
    workforce_product_name: str
    brand_asset_ref: str | None
    roles: tuple[AvatarWhiteLabelRoleProjection, ...]
    mandatory_ai_disclosure: bool = True
    disclosure_override_allowed: bool = False
    live_identity_disclosure_still_required: bool = True
    projection_only: bool = True
    identity_created: bool = False
    consent_granted: bool = False
    tenant_configuration_persisted: bool = False
    dns_domain_mutation: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False
    execution_authority: str = "none"
    mode: str = "OBSERVE"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "roles": [role.as_dict() for role in self.roles],
        }


def _role_projection(
    *,
    brand_name: str,
    template: AvatarCloneRoleTemplate,
) -> AvatarWhiteLabelRoleProjection:
    template.validate()
    return AvatarWhiteLabelRoleProjection(
        template_key=template.key,
        display_role=template.display_role,
        branded_label=f"{brand_name} {template.display_role} AI Digital Avatar",
        capability_labels=template.capability_labels,
        consultation_domains=template.consultation_domains,
    )


def project_white_label_workforce(
    config: AvatarWorkforceWhiteLabelConfig,
) -> AvatarWhiteLabelWorkforceProjection:
    config.validate()
    catalog = {
        item.key: item
        for item in clone_role_template_catalog()
    }
    keys = tuple(
        str(value).strip().lower()
        for value in config.allowed_template_keys
    )
    roles = tuple(
        _role_projection(
            brand_name=config.brand_name.strip(),
            template=catalog[key],
        )
        for key in keys
    )
    return AvatarWhiteLabelWorkforceProjection(
        tenant_id=config.tenant_id.strip(),
        brand_name=config.brand_name.strip(),
        workforce_product_name=config.workforce_product_name.strip(),
        brand_asset_ref=(
            str(config.brand_asset_ref).strip()
            if config.brand_asset_ref is not None
            else None
        ),
        roles=roles,
    )
