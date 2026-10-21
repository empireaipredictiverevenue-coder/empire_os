"""Regression guard: reusable inbound skill references existing EmpireOS owners."""
from pathlib import Path

from empire_os.skillforge_evaluation import evaluate_skill

ROOT = Path("empire_os/skills_library/skills")
NAME = "empire-ai-receptionist-revenue-recovery"


def test_skillforge_static_contract_passes_without_claiming_promotion():
    result = evaluate_skill(NAME)
    assert result["passed"] is True
    assert result["evaluation_kind"] == "static_contract_only"
    assert result["authority"] == "none"
    assert result["approved"] is False
    assert len(result["sha256"]) == 64


def test_reusable_skill_avoids_duplicate_recovery_crm_and_database():
    skill = (ROOT / NAME / "SKILL.md").read_text()
    reference = (ROOT / NAME / "references" / "existing-system-map.md").read_text()
    assert skill.startswith("---\nname: " + NAME)
    assert "## Evidence contract" in skill
    for module in (
        "inbound_revenue_recovery.py", "inbound_opportunity_intelligence.py",
        "inbound_reception_call_flow.py", "inbound_reception_intake.py",
        "inbound_reception_voice_api.py", "inbound_recovery_scorecard.py",
        "inbound_booking_workflow.py", "inbound_source_attribution.py",
    ):
        assert module in skill
    assert "EmpireDB PostgreSQL" in skill
    assert "Supabase" in skill and "Do not switch to Supabase" in skill
    assert "missed call" in skill.lower()
    assert "CRMEnquiryDraft" in skill
    assert "PENDING_HUMAN_REVIEW_NOT_SUBMITTED" in skill
    assert "no live" not in skill.lower() or "explicit" in skill.lower()
    assert "No first-party paid recovery is proven" in reference
    assert "not a deployed voice answering system" in reference
