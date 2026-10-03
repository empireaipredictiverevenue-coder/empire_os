"""Private read-only specialist consultation planning for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.departments import DepartmentSpec, default_departments
from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding


_DOMAIN_DEPARTMENT = {
    "sales": "sales_revenue",
    "product": "product",
    "technical": "engineering",
    "predictive_revenue": "data_quant",
    "research": "rd_innovation",
    "marketing": "marketing_growth",
    "strategy": "strategy",
}


def _domain(value: str) -> str:
    return str(value or "").strip().lower()


@dataclass(frozen=True)
class AvatarSpecialistConsultationRequest:
    tenant_id: str
    meeting_id: str
    avatar_id: str
    mode: AvatarMeetingMode
    consultation_domains: tuple[str, ...]
    question_evidence_ref: str
    objective_evidence_ref: str
    max_specialists: int = 3

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("consultation tenant_id required")
        if not self.meeting_id.strip() or not self.avatar_id.strip():
            raise ValueError("consultation meeting_id and avatar_id required")
        if self.mode not in {
            AvatarMeetingMode.SHADOW,
            AvatarMeetingMode.COPILOT,
        }:
            raise ValueError("consultation mode exceeds V1 authority ceiling")
        if not self.question_evidence_ref.strip():
            raise ValueError("consultation question evidence ref required")
        if not self.objective_evidence_ref.strip():
            raise ValueError("consultation objective evidence ref required")
        if self.max_specialists < 1 or self.max_specialists > len(_DOMAIN_DEPARTMENT):
            raise ValueError("max_specialists outside supported range")
        domains = tuple(_domain(value) for value in self.consultation_domains)
        if not domains or any(not value for value in domains):
            raise ValueError("consultation domains required")
        unknown = sorted(set(domains) - set(_DOMAIN_DEPARTMENT))
        if unknown:
            raise ValueError(
                "unknown consultation domain: " + ",".join(unknown)
            )


@dataclass(frozen=True)
class AvatarSpecialistConsultationLane:
    domain: str
    department_key: str
    department_name: str
    mission: str
    components: tuple[str, ...]
    agent_roles: tuple[str, ...]
    consultation_authority: str = "read_only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
@dataclass(frozen=True)
class AvatarSpecialistConsultationPlan:
    tenant_id: str
    meeting_id: str
    avatar_id: str
    mode: str
    requested_domains: tuple[str, ...]
    selected_lanes: tuple[AvatarSpecialistConsultationLane, ...]
    truncated_domains: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    read_only: bool = True
    private_to_owner: bool = True
    recommendation_only: bool = True
    department_work_enqueued: bool = False
    external_execution_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False
    execution_authority: str = "none"

    @property
    def selected_department_keys(self) -> tuple[str, ...]:
        return tuple(lane.department_key for lane in self.selected_lanes)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["selected_lanes"] = [
            lane.as_dict()
            for lane in self.selected_lanes
        ]
        value["selected_department_keys"] = list(
            self.selected_department_keys
        )
        return value


def _registry(
    departments: Iterable[DepartmentSpec] | None,
) -> dict[str, DepartmentSpec]:
    rows = tuple(
        default_departments()
        if departments is None
        else departments
    )
    result: dict[str, DepartmentSpec] = {}
    for department in rows:
        if department.key in result and result[department.key] != department:
            raise ValueError("duplicate department registry key")
        result[department.key] = department
    return result
def build_avatar_specialist_consultation_plan(
    *,
    runtime: AvatarFleetRuntimeBinding,
    request: AvatarSpecialistConsultationRequest,
    departments: Iterable[DepartmentSpec] | None = None,
) -> AvatarSpecialistConsultationPlan:
    request.validate()
    if request.tenant_id != runtime.tenant_id:
        raise PermissionError("consultation_runtime_tenant_mismatch")
    if request.avatar_id != runtime.avatar_id:
        raise PermissionError("consultation_runtime_avatar_mismatch")
    if runtime.runtime_authority != "observe":
        raise ValueError("consultation runtime authority must remain observe")
    if runtime.execution_authority != "none":
        raise ValueError("consultation runtime execution authority must remain none")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("consultation runtime contains forbidden authority")

    normalized = tuple(dict.fromkeys(
        _domain(value)
        for value in request.consultation_domains
    ))
    selected_domains = normalized[: request.max_specialists]
    truncated = normalized[request.max_specialists :]
    registry = _registry(departments)

    lanes: list[AvatarSpecialistConsultationLane] = []
    for domain in selected_domains:
        key = _DOMAIN_DEPARTMENT[domain]
        department = registry.get(key)
        if department is None:
            raise ValueError(
                f"consultation department owner missing: {key}"
            )
        lanes.append(
            AvatarSpecialistConsultationLane(
                domain=domain,
                department_key=department.key,
                department_name=department.name,
                mission=department.mission,
                components=department.components,
                agent_roles=department.agent_roles,
            )
        )

    return AvatarSpecialistConsultationPlan(
        tenant_id=request.tenant_id,
        meeting_id=request.meeting_id,
        avatar_id=request.avatar_id,
        mode=request.mode.value,
        requested_domains=normalized,
        selected_lanes=tuple(lanes),
        truncated_domains=truncated,
        evidence_refs=(
            request.question_evidence_ref,
            request.objective_evidence_ref,
        ),
    )
