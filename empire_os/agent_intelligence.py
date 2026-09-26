"""Canonical governed agent-intelligence registry for EmpireOS.

Skills and personas select knowledge and expertise only.
They never grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "empire_os" / "skills_library" / "skills"


@dataclass(frozen=True)
class SkillSpec:
    name: str
    path: str | None = None
    requires: tuple[str, ...] = ()
    recommends: tuple[str, ...] = ()
    verifies_with: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()


@dataclass(frozen=True)
class PersonaSpec:
    name: str
    mission: str
    preferred_skills: tuple[str, ...] = ()
    required_verifiers: tuple[str, ...] = ()
    success_definition: str = ""


# Reuse existing skill-library documents where they already fit.
# Empire-native skills without a mature SKILL.md remain declared graph nodes
# until their governed documents are promoted through the Knowledge Garden.
SKILLS: dict[str, SkillSpec] = {
    "architecture-first": SkillSpec("architecture-first"),
    "production-truth": SkillSpec("production-truth"),
    "evidence-truth": SkillSpec("evidence-truth"),

    "git-verification": SkillSpec(
        "git-verification",
        verifies_with=("production-truth",),
    ),

    "python-backend": SkillSpec(
        "python-backend",
        recommends=("git-verification",),
    ),

    "pytest-debugger": SkillSpec(
        "pytest-debugger",
        requires=("python-backend",),
        verifies_with=("git-verification",),
    ),

    "nextjs-engineer": SkillSpec(
        "nextjs-engineer",
        path="empire_os/skills_library/skills/frontend-design/SKILL.md",
        recommends=("git-verification",),
    ),

    "cinematic-frontend": SkillSpec(
        "cinematic-frontend",
        path="empire_os/skills_library/skills/frontend-design/SKILL.md",
        requires=("nextjs-engineer",),
        recommends=("brand-guidelines",),
        verifies_with=("visual-qa", "responsive-qa"),
    ),

    "brand-guidelines": SkillSpec(
        "brand-guidelines",
        path="empire_os/skills_library/skills/brand-guidelines/SKILL.md",
    ),

    "visual-qa": SkillSpec(
        "visual-qa",
        path="empire_os/skills_library/skills/webapp-testing/SKILL.md",
    ),

    "responsive-qa": SkillSpec(
        "responsive-qa",
        path="empire_os/skills_library/skills/webapp-testing/SKILL.md",
    ),

    "supabase": SkillSpec(
        "supabase",
        requires=("production-truth", "evidence-truth"),
        verifies_with=("git-verification",),
    ),

    "crawler-engineering": SkillSpec(
        "crawler-engineering",
        requires=("production-truth", "evidence-truth"),
        recommends=("python-backend",),
        verifies_with=("git-verification",),
    ),

    "seo-aeo": SkillSpec(
        "seo-aeo",
        requires=("evidence-truth",),
    ),

    "revenue-intelligence": SkillSpec(
        "revenue-intelligence",
        requires=("revenue-truth", "evidence-truth"),
    ),

    "revenue-truth": SkillSpec(
        "revenue-truth",
        path="empire_os/skills_library/production-revenue/SKILL.md",
        requires=("production-truth", "evidence-truth"),
    ),

    "buyer-policy-evidence": SkillSpec(
        "buyer-policy-evidence",
        requires=("evidence-truth", "revenue-truth"),
    ),

    "buyer-conversation": SkillSpec(
        "buyer-conversation",
        requires=("buyer-policy-evidence",),
        recommends=("revenue-intelligence",),
    ),

    "commercial-exchange": SkillSpec(
        "commercial-exchange",
        requires=("revenue-truth", "buyer-policy-evidence"),
    ),

    "systemd-production": SkillSpec(
        "systemd-production",
        requires=("production-truth",),
        verifies_with=("git-verification",),
    ),

    "security-review": SkillSpec(
        "security-review",
        requires=("production-truth",),
    ),
}


PERSONAS: dict[str, PersonaSpec] = {
    "senior_architect": PersonaSpec(
        name="senior_architect",
        mission="Protect system coherence and architecture-first engineering.",
        preferred_skills=(
            "architecture-first",
            "production-truth",
            "evidence-truth",
        ),
        required_verifiers=("git-verification",),
        success_definition="A coherent, evidence-bound design with explicit boundaries.",
    ),

    "backend_engineer": PersonaSpec(
        name="backend_engineer",
        mission="Implement reliable backend changes with minimal blast radius.",
        preferred_skills=(
            "python-backend",
            "pytest-debugger",
            "production-truth",
        ),
        required_verifiers=("git-verification",),
        success_definition="Focused implementation passes relevant verification.",
    ),

    "cinematic_frontend_engineer": PersonaSpec(
        name="cinematic_frontend_engineer",
        mission="Build premium performant Empire product experiences.",
        preferred_skills=(
            "cinematic-frontend",
            "nextjs-engineer",
            "brand-guidelines",
        ),
        required_verifiers=("visual-qa", "responsive-qa", "git-verification"),
        success_definition="Build passes and rendered desktop/mobile experience is verified.",
    ),

    "revenue_systems_engineer": PersonaSpec(
        name="revenue_systems_engineer",
        mission="Build revenue systems without confusing forecasts with economic truth.",
        preferred_skills=(
            "revenue-intelligence",
            "revenue-truth",
            "commercial-exchange",
        ),
        required_verifiers=("evidence-truth", "git-verification"),
        success_definition="Commercial behavior remains evidence-bound and test verified.",
    ),

    "buyer_conversation_specialist": PersonaSpec(
        name="buyer_conversation_specialist",
        mission="Advance genuine buyer conversations using buyer-stated evidence.",
        preferred_skills=(
            "buyer-conversation",
            "buyer-policy-evidence",
            "revenue-truth",
        ),
        required_verifiers=("evidence-truth",),
        success_definition="Next action is grounded in genuine buyer evidence.",
    ),

    "production_engineer": PersonaSpec(
        name="production_engineer",
        mission="Diagnose and improve runtime reliability without casual production mutation.",
        preferred_skills=(
            "systemd-production",
            "production-truth",
            "security-review",
        ),
        required_verifiers=("git-verification",),
        success_definition="Root cause and verification evidence are explicit.",
    ),

    "visual_qa": PersonaSpec(
        name="visual_qa",
        mission="Independently judge rendered interfaces rather than source intent.",
        preferred_skills=("visual-qa", "responsive-qa"),
        required_verifiers=(),
        success_definition="Rendered evidence is inspected at required viewports.",
    ),
}


def get_skill(name: str) -> SkillSpec:
    try:
        return SKILLS[name]
    except KeyError as exc:
        raise KeyError(f"unknown Empire skill: {name}") from exc


def get_persona(name: str) -> PersonaSpec:
    try:
        return PERSONAS[name]
    except KeyError as exc:
        raise KeyError(f"unknown Empire persona: {name}") from exc


def resolve_skill_graph(names: Iterable[str]) -> tuple[str, ...]:
    """Resolve required dependencies deterministically.

    This selects knowledge only. It does not calculate or grant authority.
    """
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"skill dependency cycle detected at {name}")

        spec = get_skill(name)
        visiting.add(name)

        for dependency in spec.requires:
            visit(dependency)

        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in names:
        visit(name)

    return tuple(ordered)


def skills_for_persona(name: str) -> tuple[str, ...]:
    return resolve_skill_graph(get_persona(name).preferred_skills)


def skill_document_path(name: str) -> Path | None:
    spec = get_skill(name)
    if spec.path is None:
        return None

    path = (ROOT / spec.path).resolve()

    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"skill path escapes repository: {spec.path}") from exc

    return path


def load_skill_document(name: str, *, max_chars: int = 20_000) -> str | None:
    path = skill_document_path(name)

    if path is None or not path.is_file():
        return None

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )[:max_chars]


def skill_graph_snapshot() -> dict[str, dict[str, object]]:
    return {
        name: {
            "path": spec.path,
            "requires": spec.requires,
            "recommends": spec.recommends,
            "verifies_with": spec.verifies_with,
            "conflicts_with": spec.conflicts_with,
            "grants_authority": False,
        }
        for name, spec in sorted(SKILLS.items())
    }
