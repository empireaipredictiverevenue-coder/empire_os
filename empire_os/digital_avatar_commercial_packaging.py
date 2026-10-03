"""Commercial packaging projections for Digital Avatar products.

Package definitions contain capabilities only. Canonical catalog and verified
tenant entitlement evidence supply price/economics and purchased limits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.commercial_product_catalog import (
    assess_catalog_item,
    public_catalog_projection,
)
from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_clone_role_templates import (
    clone_role_template_catalog,
)


@dataclass(frozen=True)
class AvatarCommercialPackageSpec:
    key: str
    product_code: str
    product_name: str
    feature_keys: tuple[str, ...]
    allowed_meeting_modes: tuple[str, ...]
    supports_white_label: bool
    def validate(self) -> None:
        if not self.key.strip() or not self.product_code.strip():
            raise ValueError("avatar package key/product_code required")
        if not self.product_name.strip() or not self.feature_keys:
            raise ValueError("avatar package name/features required")
        if len(self.feature_keys) != len(set(self.feature_keys)):
            raise ValueError("avatar package features must be unique")
        modes = tuple(str(value).strip().lower() for value in self.allowed_meeting_modes)
        if not modes or len(modes) != len(set(modes)):
            raise ValueError("avatar package meeting modes invalid")
        allowed = {
            AvatarMeetingMode.SHADOW.value,
            AvatarMeetingMode.COPILOT.value,
        }
        if any(mode not in allowed for mode in modes):
            raise ValueError("avatar package mode exceeds V1 authority ceiling")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


_PACKAGES = (
    AvatarCommercialPackageSpec(
        key="copilot",
        product_code="digital_avatar_copilot",
        product_name="Digital Avatar Copilot",
        feature_keys=(
            "grounded_meeting_intelligence",
            "private_specialist_consultation",
            "verified_meeting_usage",
        ),
        allowed_meeting_modes=("shadow", "copilot"),
        supports_white_label=False,
    ),
    AvatarCommercialPackageSpec(
        key="workforce",
        product_code="digital_avatar_workforce",
        product_name="Digital Avatar Workforce",
        feature_keys=(
            "clone_role_templates",
            "fleet_routing",
            "concurrency_planning",
            "continuity_memory",
            "private_specialist_consultation",
            "verified_meeting_usage",
        ),
        allowed_meeting_modes=("shadow", "copilot"),
        supports_white_label=False,
    ),
    AvatarCommercialPackageSpec(
        key="white_label_workforce",
        product_code="digital_avatar_white_label_workforce",
        product_name="Digital Avatar White-Label Workforce",
        feature_keys=(
            "clone_role_templates",
            "fleet_routing",
            "concurrency_planning",
            "continuity_memory",
            "private_specialist_consultation",
            "verified_meeting_usage",
            "white_label_projection",
        ),
        allowed_meeting_modes=("shadow", "copilot"),
        supports_white_label=True,
    ),
)
@dataclass(frozen=True)
class AvatarCommercialEntitlementEvidence:
    verified: bool
    reference: str | None
    verified_at: str | None
    tenant_id: str
    product_code: str
    allowed_role_template_keys: tuple[str, ...]
    allowed_meeting_modes: tuple[str, ...]
    max_active_avatars: int | None
    included_verified_meetings_per_month: int | None
    white_label_allowed: bool | None

    def blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.verified:
            blockers.append("entitlement_unverified")
        if not str(self.reference or "").strip():
            blockers.append("entitlement_reference_missing")
        if not str(self.verified_at or "").strip():
            blockers.append("entitlement_verified_at_missing")
        if not self.tenant_id.strip():
            blockers.append("entitlement_tenant_missing")
        if not self.product_code.strip():
            blockers.append("entitlement_product_missing")
        known_roles = {item.key for item in clone_role_template_catalog()}
        roles = tuple(str(value).strip() for value in self.allowed_role_template_keys)
        if not roles:
            blockers.append("entitlement_roles_missing")
        elif any(role not in known_roles for role in roles):
            blockers.append("entitlement_role_unknown")
        elif len(roles) != len(set(roles)):
            blockers.append("entitlement_roles_duplicate")

        modes = tuple(str(value).strip().lower() for value in self.allowed_meeting_modes)
        allowed_modes = {
            AvatarMeetingMode.SHADOW.value,
            AvatarMeetingMode.COPILOT.value,
        }
        if not modes:
            blockers.append("entitlement_meeting_modes_missing")
        elif any(mode not in allowed_modes for mode in modes):
            blockers.append("entitlement_mode_exceeds_v1")
        elif len(modes) != len(set(modes)):
            blockers.append("entitlement_meeting_modes_duplicate")

        if self.max_active_avatars is None:
            blockers.append("entitlement_avatar_limit_missing")
        elif self.max_active_avatars < 1:
            blockers.append("entitlement_avatar_limit_invalid")
        if self.included_verified_meetings_per_month is None:
            blockers.append("entitlement_meeting_limit_missing")
        elif self.included_verified_meetings_per_month < 0:
            blockers.append("entitlement_meeting_limit_invalid")
        if self.white_label_allowed is None:
            blockers.append("entitlement_white_label_flag_missing")
        return tuple(blockers)
@dataclass(frozen=True)
class AvatarCommercialPackageProjection:
    tenant_id: str
    package_key: str
    product_code: str
    product_name: str
    feature_keys: tuple[str, ...]
    allowed_role_template_keys: tuple[str, ...]
    allowed_meeting_modes: tuple[str, ...]
    max_active_avatars: int | None
    included_verified_meetings_per_month: int | None
    white_label_allowed: bool | None
    catalog_product_id: str | None
    catalog_version_id: str | None
    catalog_version: int | None
    catalog_price: Mapping[str, Any]
    commercially_ready: bool
    entitlement_ready: bool
    blockers: tuple[str, ...]
    actual_revenue: bool = False
    checkout_created: bool = False
    subscription_mutation: bool = False
    payment_request_creation: bool = False
    funds_movement: bool = False
    recognized_revenue: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def avatar_commercial_package_catalog() -> tuple[AvatarCommercialPackageSpec, ...]:
    seen: set[str] = set()
    codes: set[str] = set()
    for package in _PACKAGES:
        package.validate()
        if package.key in seen or package.product_code in codes:
            raise ValueError("duplicate avatar commercial package")
        seen.add(package.key)
        codes.add(package.product_code)
    return _PACKAGES


def get_avatar_commercial_package(key: str) -> AvatarCommercialPackageSpec:
    clean = str(key or "").strip().lower()
    for package in avatar_commercial_package_catalog():
        if package.key == clean:
            return package
    raise KeyError(f"unknown avatar commercial package: {clean}")


def project_avatar_commercial_package(
    *,
    tenant_id: str,
    package_key: str,
    catalog_row: Mapping[str, Any] | None,
    entitlement: AvatarCommercialEntitlementEvidence | None,
) -> AvatarCommercialPackageProjection:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("avatar commercial tenant_id required")
    package = get_avatar_commercial_package(package_key)
    blockers: list[str] = []
    assessed: dict[str, Any] | None = None
    public_price: Mapping[str, Any] = {}
    if catalog_row is None:
        blockers.append("catalog_product_missing")
    else:
        if str(catalog_row.get("product_code") or "").strip() != package.product_code:
            raise ValueError("avatar package/catalog product mismatch")
        assessed = assess_catalog_item(catalog_row)
        blockers.extend(
            f"catalog:{value}"
            for value in assessed.get("readiness_blockers") or ()
        )
        public = public_catalog_projection({"products": [assessed]})
        if public.get("count") == 1:
            public_price = dict(public["products"][0].get("price") or {})

    entitlement_ready = False
    roles: tuple[str, ...] = ()
    modes: tuple[str, ...] = ()
    max_avatars = None
    included_meetings = None
    white_label_allowed = None
    if entitlement is None:
        blockers.append("entitlement_missing")
    else:
        if entitlement.tenant_id != tenant:
            raise PermissionError("avatar entitlement tenant mismatch")
        if entitlement.product_code != package.product_code:
            raise ValueError("avatar entitlement product mismatch")
        entitlement_blockers = entitlement.blockers()
        blockers.extend(entitlement_blockers)
        package_modes = set(package.allowed_meeting_modes)
        requested_modes = tuple(
            str(value).strip().lower()
            for value in entitlement.allowed_meeting_modes
        )
        if any(mode not in package_modes for mode in requested_modes):
            blockers.append("entitlement_mode_not_in_package")
        if entitlement.white_label_allowed and not package.supports_white_label:
            blockers.append("entitlement_white_label_not_in_package")

        roles = tuple(entitlement.allowed_role_template_keys)
        modes = requested_modes
        max_avatars = entitlement.max_active_avatars
        included_meetings = entitlement.included_verified_meetings_per_month
        white_label_allowed = entitlement.white_label_allowed
        entitlement_ready = not any(
            blocker.startswith("entitlement_")
            for blocker in blockers
        )

    ordered = tuple(dict.fromkeys(blockers))
    commercially_ready = not ordered

    return AvatarCommercialPackageProjection(
        tenant_id=tenant,
        package_key=package.key,
        product_code=package.product_code,
        product_name=package.product_name,
        feature_keys=package.feature_keys,
        allowed_role_template_keys=roles,
        allowed_meeting_modes=modes,
        max_active_avatars=max_avatars,
        included_verified_meetings_per_month=included_meetings,
        white_label_allowed=white_label_allowed,
        catalog_product_id=(
            str(assessed.get("product_id") or "").strip() or None
            if assessed is not None else None
        ),
        catalog_version_id=(
            str(assessed.get("version_id") or "").strip() or None
            if assessed is not None else None
        ),
        catalog_version=(
            int(assessed["version"])
            if assessed is not None and assessed.get("version") is not None
            else None
        ),
        catalog_price=public_price,
        commercially_ready=commercially_ready,
        entitlement_ready=entitlement_ready,
        blockers=ordered,
    )
