"""Database role and grant parity for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RoleSpec:
    name: str
    can_login: bool
    superuser: bool = False
    inherit: bool = False
    create_role: bool = False
    create_db: bool = False
    replication: bool = False
    bypass_rls: bool = False
    member_of: tuple[str, ...] = ()
    admin_memberships: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectGrant:
    grantee: str
    object_kind: str
    object_name: str
    privileges: tuple[str, ...]


def role_safety_findings(roles: Iterable[RoleSpec]) -> tuple[str, ...]:
    findings: list[str] = []
    for role in roles:
        if not role.name.startswith("empire_"):
            continue

        if role.superuser:
            findings.append(f"superuser_forbidden:{role.name}")
        if role.create_role:
            findings.append(f"createrole_forbidden:{role.name}")
        if role.create_db:
            findings.append(f"createdb_forbidden:{role.name}")
        if role.replication:
            findings.append(f"replication_forbidden:{role.name}")
        if role.bypass_rls:
            findings.append(f"bypassrls_forbidden:{role.name}")
        if role.admin_memberships:
            findings.append(f"admin_membership_forbidden:{role.name}")

        if role.name.endswith("_login"):
            capability = role.name.removesuffix("_login")
            if not role.can_login:
                findings.append(f"login_role_cannot_login:{role.name}")
            if role.member_of != (capability,):
                findings.append(f"login_membership_mismatch:{role.name}")
        elif role.can_login:
            findings.append(f"capability_role_must_be_nologin:{role.name}")

    return tuple(sorted(findings))


def compare_roles(
    source: Iterable[RoleSpec],
    target: Iterable[RoleSpec],
) -> dict[str, object]:
    source_by_name = {role.name: role for role in source}
    target_by_name = {role.name: role for role in target}
    findings: list[str] = list(role_safety_findings(target_by_name.values()))

    for name, source_role in sorted(source_by_name.items()):
        target_role = target_by_name.get(name)
        if target_role is None:
            findings.append(f"missing_role:{name}")
            continue
        if source_role != target_role:
            findings.append(f"role_mismatch:{name}")

    extra_roles = sorted(set(target_by_name) - set(source_by_name))

    return {
        "schema_version": "empire.data-cloud-role-parity.v1",
        "compatible": not findings,
        "findings": sorted(findings),
        "extra_target_roles": extra_roles,
    }


def _grant_key(grant: ObjectGrant) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        grant.grantee,
        grant.object_kind,
        grant.object_name,
        tuple(sorted(grant.privileges)),
    )


def compare_grants(
    source: Iterable[ObjectGrant],
    target: Iterable[ObjectGrant],
) -> dict[str, object]:
    source_keys = {_grant_key(grant) for grant in source}
    target_keys = {_grant_key(grant) for grant in target}

    missing = sorted(source_keys - target_keys)
    extra = sorted(target_keys - source_keys)

    findings = [
        f"missing_grant:{item[0]}:{item[1]}:{item[2]}"
        for item in missing
    ]
    findings.extend(
        f"unexpected_grant:{item[0]}:{item[1]}:{item[2]}"
        for item in extra
    )

    return {
        "schema_version": "empire.data-cloud-grant-parity.v1",
        "compatible": not findings,
        "findings": findings,
        "missing_count": len(missing),
        "unexpected_count": len(extra),
    }
