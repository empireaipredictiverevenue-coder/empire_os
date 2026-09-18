"""Capability profiles for Empire Coder tasks."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    READ_REPO = "read_repo"
    SEARCH_REPO = "search_repo"
    CREATE_PATCH = "create_patch"
    RUN_SAFE_COMMAND = "run_safe_command"
    RUN_TESTS = "run_tests"
    GIT_READ = "git_read"
    GIT_WRITE = "git_write"
    NETWORK = "network"
    SERVICE_CONTROL = "service_control"
    PRODUCTION_DB = "production_db"
    OUTBOUND = "outbound"
    FUNDS = "funds"


@dataclass(frozen=True)
class PermissionProfile:
    name: str
    capabilities: frozenset[Capability]

    def allows(self, capability: Capability) -> bool:
        return capability in self.capabilities


OBSERVE_DEVELOPER = PermissionProfile(
    "observe_developer",
    frozenset({
        Capability.READ_REPO,
        Capability.SEARCH_REPO,
        Capability.CREATE_PATCH,
        Capability.RUN_SAFE_COMMAND,
        Capability.RUN_TESTS,
        Capability.GIT_READ,
    }),
)

REVIEW_ONLY = PermissionProfile(
    "review_only",
    frozenset({
        Capability.READ_REPO,
        Capability.SEARCH_REPO,
        Capability.RUN_TESTS,
        Capability.GIT_READ,
    }),
)

FORBIDDEN_WITHOUT_HUMAN_APPROVAL = frozenset({
    Capability.GIT_WRITE,
    Capability.NETWORK,
    Capability.SERVICE_CONTROL,
    Capability.PRODUCTION_DB,
    Capability.OUTBOUND,
    Capability.FUNDS,
})
