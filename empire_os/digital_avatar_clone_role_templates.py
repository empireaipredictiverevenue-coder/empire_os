"""Authority-free product role templates for Digital Avatar clone fleets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_avatar_fleet import AvatarFleetBinding


@dataclass(frozen=True)
class AvatarCloneRoleTemplate:
    key: str
    display_role: str
    capability_labels: tuple[str, ...]
    consultation_domains: tuple[str, ...]
    mode: str = "OBSERVE"
    identity_created: bool = False
    consent_granted: bool = False
    meeting_authority: str = "none"
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    execution_authority: str = "none"

    def validate(self) -> None:
        if not self.key.strip() or not self.display_role.strip():
            raise ValueError("clone role template key/display_role required")
        if not self.capability_labels:
            raise ValueError("clone role template capabilities required")
        if not self.consultation_domains:
            raise ValueError("clone role template consultation domains required")
        for name, values in (
            ("capability", self.capability_labels),
            ("consultation", self.consultation_domains),
        ):
            cleaned = tuple(str(value).strip().lower() for value in values)
            if any(not value for value in cleaned):
                raise ValueError(f"clone role template {name} values required")
            if len(cleaned) != len(set(cleaned)):
                raise ValueError(f"clone role template {name} values must be unique")
        if (
            self.identity_created
            or self.consent_granted
            or self.meeting_authority != "none"
            or self.speech_execution_allowed
            or self.commercial_execution_allowed
            or self.payment_execution_allowed
            or self.execution_authority != "none"
        ):
            raise ValueError("clone role template grants forbidden authority")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


_TEMPLATES = (
    AvatarCloneRoleTemplate(
        key="founder_executive",
        display_role="Founder / Executive",
        capability_labels=("founder", "strategy", "sales", "product"),
        consultation_domains=(
            "strategy",
            "sales",
            "product",
            "predictive_revenue",
        ),
    ),
    AvatarCloneRoleTemplate(
        key="sales_closer",
        display_role="Sales / Closer",
        capability_labels=(
            "sales",
            "qualification",
            "objection_handling",
            "product",
        ),
        consultation_domains=("sales", "product", "predictive_revenue"),
    ),
    AvatarCloneRoleTemplate(
        key="account_manager",
        display_role="Account Manager",
        capability_labels=("account_management", "customer_success", "product"),
        consultation_domains=("product", "sales"),
    ),
    AvatarCloneRoleTemplate(
        key="product_specialist",
        display_role="Product Specialist",
        capability_labels=("product", "discovery", "solution_design"),
        consultation_domains=("product", "technical", "research"),
    ),
    AvatarCloneRoleTemplate(
        key="technical_specialist",
        display_role="Technical Specialist",
        capability_labels=("technical", "integration", "architecture"),
        consultation_domains=("technical", "product", "research"),
    ),
)


@dataclass(frozen=True)
class AvatarCloneRoleProposal:
    tenant_id: str
    avatar_id: str
    owner_ref: str
    owner_name: str
    owner_consent_evidence_ref: str
    template_key: str
    display_role: str
    capability_labels: tuple[str, ...]
    default_consultation_domains: tuple[str, ...]
    status: str = "active"
    proposal_only: bool = True
    identity_created: bool = False
    consent_granted: bool = False
    meeting_authority: str = "none"
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    execution_authority: str = "none"

    def validate(self) -> None:
        if not all(
            str(value).strip()
            for value in (
                self.tenant_id,
                self.avatar_id,
                self.owner_ref,
                self.owner_name,
                self.owner_consent_evidence_ref,
                self.template_key,
            )
        ):
            raise ValueError("clone role proposal tenant/avatar/owner consent required")
        if self.status not in {"active", "disabled"}:
            raise ValueError("clone role proposal status invalid")
        if (
            self.proposal_only is not True
            or self.identity_created
            or self.consent_granted
            or self.meeting_authority != "none"
            or self.speech_execution_allowed
            or self.commercial_execution_allowed
            or self.payment_execution_allowed
            or self.execution_authority != "none"
        ):
            raise ValueError("clone role proposal grants forbidden authority")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def to_fleet_binding(self) -> AvatarFleetBinding:
        self.validate()
        binding = AvatarFleetBinding(
            tenant_id=self.tenant_id,
            avatar_id=self.avatar_id,
            owner_ref=self.owner_ref,
            owner_name=self.owner_name,
            owner_consent_evidence_ref=self.owner_consent_evidence_ref,
            capability_labels=self.capability_labels,
            status=self.status,
        )
        binding.validate()
        return binding


def clone_role_template_catalog() -> tuple[AvatarCloneRoleTemplate, ...]:
    seen: set[str] = set()
    for template in _TEMPLATES:
        template.validate()
        if template.key in seen:
            raise ValueError("duplicate clone role template key")
        seen.add(template.key)
    return _TEMPLATES


def get_clone_role_template(key: str) -> AvatarCloneRoleTemplate:
    clean = str(key or "").strip().lower()
    for template in clone_role_template_catalog():
        if template.key == clean:
            return template
    raise KeyError(f"unknown clone role template: {clean}")


def propose_clone_role(
    *,
    template_key: str,
    tenant_id: str,
    avatar_id: str,
    owner_ref: str,
    owner_name: str,
    owner_consent_evidence_ref: str,
    status: str = "active",
) -> AvatarCloneRoleProposal:
    template = get_clone_role_template(template_key)
    proposal = AvatarCloneRoleProposal(
        tenant_id=str(tenant_id or "").strip(),
        avatar_id=str(avatar_id or "").strip(),
        owner_ref=str(owner_ref or "").strip(),
        owner_name=str(owner_name or "").strip(),
        owner_consent_evidence_ref=str(
            owner_consent_evidence_ref or ""
        ).strip(),
        template_key=template.key,
        display_role=template.display_role,
        capability_labels=template.capability_labels,
        default_consultation_domains=template.consultation_domains,
        status=status,
    )
    proposal.validate()
    return proposal
