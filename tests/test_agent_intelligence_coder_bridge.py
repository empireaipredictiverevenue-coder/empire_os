from pathlib import Path

import pytest

from empire_os.agent_intelligence import (
    get_persona,
    skills_for_persona,
)
from empire_os.coder.skills import SkillLoader


ROOT = Path(__file__).resolve().parents[1]


def test_core_soul_exists_and_separates_authority():
    text = (
        ROOT
        / "empire_os/agent_intelligence/EMPIRE_CORE_SOUL.md"
    ).read_text()

    assert "Completion means verified outcome" in text
    assert "UNKNOWN remains UNKNOWN" in text
    assert "Skill is not permission." in text
    assert "Never expand your own authority." in text


def test_canonical_persona_documents_exist():
    root = ROOT / "empire_os/agent_intelligence/personas"

    expected = {
        "senior_architect.md",
        "cinematic_frontend_engineer.md",
        "revenue_systems_engineer.md",
        "production_engineer.md",
        "buyer_conversation_specialist.md",
    }

    assert expected <= {p.name for p in root.glob("*.md")}


def test_persona_graph_can_drive_skill_selection():
    skills = skills_for_persona("cinematic_frontend_engineer")

    assert "nextjs-engineer" in skills
    assert "cinematic-frontend" in skills


def test_native_skill_still_requires_active_garden_path():
    loader = SkillLoader(ROOT, active_knowledge_paths=())

    with pytest.raises(PermissionError):
        loader.load("cinematic-frontend")


def test_native_skill_loads_when_existing_document_is_active():
    relative = (
        "empire_os/skills_library/skills/"
        "frontend-design/SKILL.md"
    )

    loader = SkillLoader(
        ROOT,
        active_knowledge_paths=(relative,),
    )

    document = loader.load("cinematic-frontend")

    assert document.name == "cinematic-frontend"
    assert document.path == relative
    assert document.content


def test_available_exposes_native_skill_only_when_active():
    relative = (
        "empire_os/skills_library/skills/"
        "frontend-design/SKILL.md"
    )

    inactive = SkillLoader(ROOT, active_knowledge_paths=())
    active = SkillLoader(
        ROOT,
        active_knowledge_paths=(relative,),
    )

    assert "cinematic-frontend" not in inactive.available()
    assert "cinematic-frontend" in active.available()


def test_persona_remains_metadata_not_authority():
    persona = get_persona("production_engineer")

    assert persona.name == "production_engineer"
    assert not hasattr(persona, "execution_authority")
