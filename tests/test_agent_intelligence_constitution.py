from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION = ROOT / "docs/agent_intelligence/EMPIRE_AGENT_CONSTITUTION.md"
SKILLS = ROOT / "docs/agent_intelligence/SKILL_ARCHITECTURE.md"
PERSONA = ROOT / "docs/agent_intelligence/PERSONA_CONTRACT.md"


def test_constitution_exists_and_preserves_truth_rules():
    text = CONSTITUTION.read_text()
    assert "UNKNOWN remains UNKNOWN" in text
    assert "Completion means a verified outcome" in text
    assert "Persona Is Not Authority" in text
    assert "Self-modification is never self-approval" in text
    assert "Forecasts, scores, opportunities" in text


def test_constitution_preserves_architecture_first_sequence():
    text = CONSTITUTION.read_text()
    for step in (
        "DIAGRAM",
        "ARCHITECTURE CONTRACT",
        "WORKER ASSIGNMENT",
        "IMPLEMENT",
        "INDEPENDENT VERIFY",
        "LIVE VERIFY",
        "CHECKLIST DONE",
    ):
        assert step in text


def test_skill_architecture_separates_skill_from_authority():
    text = SKILLS.read_text()
    assert "Graph edges select knowledge, not authority." in text
    assert "No skill self-promotes." in text
    assert "cinematic-frontend" in text
    assert "buyer-policy-evidence" in text
    assert "revenue-truth" in text


def test_persona_contract_does_not_grant_authority():
    text = PERSONA.read_text()
    assert "Persona is expertise, not authority." in text
    assert "outbound send authority" in text
    assert "payment/funds authority" in text
    assert "migration authority" in text
