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


def test_old_active_garden_document_no_longer_bypasses_skillforge():
    relative = 'empire_os/skills_library/skills/frontend-design/SKILL.md'
    loader = SkillLoader(ROOT, active_knowledge_paths=(relative,))
    with pytest.raises(PermissionError, match='approved digest'):
        loader.load('cinematic-frontend')
    assert 'cinematic-frontend' not in loader.available()


def test_empire_coder_loads_only_pinned_complete_skill(tmp_path):
    from hashlib import sha256
    import json
    (tmp_path/'.git').mkdir()
    name='empire-engineering-verification'
    relative=f'empire_os/skills_library/skills/{name}/SKILL.md'
    folder=tmp_path/'empire_os/skills_library/skills'/name
    folder.mkdir(parents=True)
    body='# Full verified skill\nKeep OBSERVE, validate evidence and founder authority.'
    (folder/'SKILL.md').write_text(body)
    registry_path=tmp_path/'config/skill_trust_registry.json'
    registry_path.parent.mkdir()
    registry_path.write_text(json.dumps({'schema_version':'empire.skill_trust.v1',
        'approved_skills':{name:{'status':'approved','sha256':sha256(body.encode()).hexdigest()}}}))
    loader=SkillLoader(tmp_path,active_knowledge_paths=(relative,))
    assert loader.available()==(name,)
    assert loader.load(name).content==body
    with pytest.raises(PermissionError,match='bounded complete'):
        loader.load(name,max_chars=5)
    (folder/'SKILL.md').write_text('changed')
    with pytest.raises(PermissionError,match='approved digest'):
        loader.load(name)
    assert loader.available()==()


def test_persona_remains_metadata_not_authority():
    persona = get_persona("production_engineer")

    assert persona.name == "production_engineer"
    assert not hasattr(persona, "execution_authority")
