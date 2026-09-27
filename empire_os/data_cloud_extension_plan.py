"""PostgreSQL extension portability planning for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class ExtensionClass(str, Enum):
    CORE = "core"
    PORTABLE = "portable"
    OPERATIONAL = "operational"
    VENDOR_SPECIFIC = "vendor_specific"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExtensionObservation:
    name: str
    version: str


@dataclass(frozen=True)
class ExtensionPlan:
    name: str
    source_version: str
    classification: ExtensionClass
    required_by_schema: bool
    action: str
    cutover_blocked: bool = False

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        return payload


_CLASSIFICATION = {
    "plpgsql": ExtensionClass.CORE,
    "pgcrypto": ExtensionClass.PORTABLE,
    "uuid-ossp": ExtensionClass.PORTABLE,
    "postgis": ExtensionClass.PORTABLE,
    "vector": ExtensionClass.PORTABLE,
    "pg_stat_statements": ExtensionClass.OPERATIONAL,
    "supabase_vault": ExtensionClass.VENDOR_SPECIFIC,
}


def classify_extension(name: str) -> ExtensionClass:
    return _CLASSIFICATION.get(name, ExtensionClass.UNKNOWN)


def plan_extensions(
    observed: Iterable[ExtensionObservation],
    *,
    required_by_schema: Iterable[str] = (),
) -> tuple[ExtensionPlan, ...]:
    required = {str(name) for name in required_by_schema}
    plans: list[ExtensionPlan] = []

    for extension in sorted(observed, key=lambda row: row.name):
        classification = classify_extension(extension.name)
        is_required = extension.name in required

        if classification is ExtensionClass.CORE:
            action = "provided_by_postgresql"
            blocked = False
        elif classification is ExtensionClass.PORTABLE:
            action = "install_and_verify" if is_required else "install_if_needed"
            blocked = False
        elif classification is ExtensionClass.OPERATIONAL:
            action = "install_for_observability"
            blocked = False
        elif classification is ExtensionClass.VENDOR_SPECIFIC:
            action = "replace_with_empire_capability"
            blocked = is_required
        else:
            action = "manual_compatibility_review"
            blocked = is_required

        plans.append(
            ExtensionPlan(
                name=extension.name,
                source_version=extension.version,
                classification=classification,
                required_by_schema=is_required,
                action=action,
                cutover_blocked=blocked,
            )
        )

    return tuple(plans)


def extension_cutover_blockers(
    plans: Iterable[ExtensionPlan],
) -> tuple[str, ...]:
    return tuple(
        plan.name
        for plan in plans
        if plan.cutover_blocked
    )
