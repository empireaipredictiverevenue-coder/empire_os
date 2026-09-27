"""Specialist engineering roles for governed multi-agent development."""
from __future__ import annotations

from dataclasses import dataclass

from .permissions import OBSERVE_DEVELOPER, REVIEW_ONLY, PermissionProfile


@dataclass(frozen=True)
class CoderRole:
    name: str
    mission: str
    permission_profile: PermissionProfile
    can_patch: bool
    can_verify: bool
    required_outputs: tuple[str, ...]


ARCHITECT = CoderRole(
    "architect",
    "Design implementation strategy from Blueprint and repository evidence.",
    REVIEW_ONLY,
    False,
    False,
    ("plan", "constraints", "affected_components"),
)

BACKEND = CoderRole(
    "backend",
    "Implement backend/API/database/service changes within assigned files.",
    OBSERVE_DEVELOPER,
    True,
    False,
    ("patch", "tests", "risk_notes"),
)

FRONTEND = CoderRole(
    "frontend",
    "Implement governed UI/client changes within assigned files.",
    OBSERVE_DEVELOPER,
    True,
    False,
    ("patch", "tests", "ux_notes"),
)

QA = CoderRole(
    "qa",
    "Select and run focused regression tests and identify missing coverage.",
    REVIEW_ONLY,
    False,
    True,
    ("test_plan", "results", "gaps"),
)

SECURITY = CoderRole(
    "security",
    "Review candidate changes for secrets, authority expansion, unsafe execution and data exposure.",
    REVIEW_ONLY,
    False,
    True,
    ("findings", "severity", "verdict"),
)

REVIEWER = CoderRole(
    "reviewer",
    "Independently compare the diff with objective and Blueprint constraints.",
    REVIEW_ONLY,
    False,
    True,
    ("verdict", "reasons", "warnings"),
)

ROLES = {
    role.name: role
    for role in (ARCHITECT, BACKEND, FRONTEND, QA, SECURITY, REVIEWER)
}
