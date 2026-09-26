from empire_os.agent_intelligence import (
    PERSONAS,
    SKILLS,
    get_persona,
    get_skill,
    load_skill_document,
    resolve_skill_graph,
    skill_graph_snapshot,
    skills_for_persona,
)


def test_core_native_skills_registered():
    expected = {
        "architecture-first",
        "production-truth",
        "evidence-truth",
        "git-verification",
        "cinematic-frontend",
        "visual-qa",
        "revenue-truth",
        "buyer-policy-evidence",
        "systemd-production",
        "security-review",
    }
    assert expected <= set(SKILLS)


def test_persona_and_skill_are_separate_concepts():
    persona = get_persona("cinematic_frontend_engineer")
    skill = get_skill("cinematic-frontend")

    assert persona.name == "cinematic_frontend_engineer"
    assert skill.name == "cinematic-frontend"
    assert "cinematic-frontend" in persona.preferred_skills


def test_skill_graph_resolves_required_dependencies_first():
    resolved = resolve_skill_graph(("cinematic-frontend",))

    assert resolved.index("nextjs-engineer") < resolved.index(
        "cinematic-frontend"
    )


def test_revenue_graph_includes_truth_dependencies():
    resolved = resolve_skill_graph(("revenue-intelligence",))

    assert "production-truth" in resolved
    assert "evidence-truth" in resolved
    assert "revenue-truth" in resolved
    assert resolved[-1] == "revenue-intelligence"


def test_persona_resolution_is_deterministic():
    first = skills_for_persona("revenue_systems_engineer")
    second = skills_for_persona("revenue_systems_engineer")

    assert first == second
    assert len(first) == len(set(first))


def test_registry_never_grants_authority():
    snapshot = skill_graph_snapshot()

    assert snapshot
    assert all(
        item["grants_authority"] is False
        for item in snapshot.values()
    )


def test_existing_skill_documents_are_reused():
    assert load_skill_document("cinematic-frontend")
    assert load_skill_document("visual-qa")
    assert load_skill_document("brand-guidelines")


def test_native_skill_without_promoted_document_is_metadata_only():
    assert load_skill_document("production-truth") is None


def test_persona_registry_has_initial_specialists():
    assert {
        "senior_architect",
        "backend_engineer",
        "cinematic_frontend_engineer",
        "revenue_systems_engineer",
        "buyer_conversation_specialist",
        "production_engineer",
        "visual_qa",
    } <= set(PERSONAS)
