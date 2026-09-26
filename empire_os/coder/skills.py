"""Garden-governed skill retrieval for Empire Coder."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .policy import resolve_workspace


_CURATED_SKILLS = {
    "tooling": "empire_os/skills_library/skills/mcp-builder/SKILL.md",
    "verification": "empire_os/skills_library/skills/webapp-testing/SKILL.md",
}


def _native_skill_paths() -> dict[str, str]:
    """Return promoted-document paths from the canonical Empire registry.

    The registry selects knowledge only. Knowledge Garden ACTIVE state still
    controls whether the document can actually be loaded.
    """
    from empire_os.agent_intelligence import SKILLS

    return {
        name: spec.path
        for name, spec in SKILLS.items()
        if spec.path
    }


EMPIRE_CODER_PERSONA = """You are Empire Coder, the governed developer intelligence layer for EmpireOS.

Inspect before modifying. Use Blueprint v6 and repository AGENTS.md as architectural authority.
Prefer targeted patches over whole-file rewrites. Preserve unrelated user work.
Production, outbound, payment, secrets, migrations, service control and deployment remain human-gated.
A task is not complete because code exists; verification and diff review are mandatory.
Never fabricate test results, runtime evidence, business data, model output or repository state.
Self-improvement is controlled: propose and verify patches, never recursively grant yourself more authority.
"""


@dataclass(frozen=True)
class SkillDocument:
    name: str
    path: str
    content: str


class SkillLoader:
    def __init__(
        self,
        workspace: str | Path,
        *,
        active_knowledge_paths: Iterable[str] = (),
    ) -> None:
        self.workspace = resolve_workspace(workspace)
        self.active_knowledge_paths = set(
            str(path) for path in active_knowledge_paths
        )

    def set_active_knowledge_paths(
        self,
        paths: Iterable[str],
    ) -> None:
        self.active_knowledge_paths = set(str(path) for path in paths)

    def load(
        self,
        name: str,
        *,
        max_chars: int = 20_000,
    ) -> SkillDocument:
        catalog = {
            **_CURATED_SKILLS,
            **_native_skill_paths(),
        }
        try:
            relative = catalog[name]
        except KeyError as exc:
            raise KeyError(
                f"unknown governed Empire Coder skill: {name}"
            ) from exc
        if relative not in self.active_knowledge_paths:
            raise PermissionError(
                f"skill is not ACTIVE in knowledge garden: {relative}"
            )
        path = self.workspace / relative
        content = path.read_text(
            encoding="utf-8", errors="replace"
        )[:max_chars]
        return SkillDocument(name, relative, content)

    def available(self) -> tuple[str, ...]:
        catalog = {
            **_CURATED_SKILLS,
            **_native_skill_paths(),
        }
        return tuple(
            name
            for name, path in sorted(catalog.items())
            if path in self.active_knowledge_paths
        )

    def persona(self) -> str:
        return EMPIRE_CODER_PERSONA
