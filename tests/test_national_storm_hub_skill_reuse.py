"""Exact, read-only reuse of existing Empire SkillForge packs for Storm Hub."""
from pathlib import Path

import pytest

from empire_os.skill_exchange import (
    COMPONENT_TASKS,
    discover_task_skills,
    recommend_work_item_skills,
)


EXPECTED = {
    "national_storm_hub_weather_evidence": ("market_intelligence", "empire-evidence-verification"),
    "national_storm_hub_storm_predictor": ("data_quant", "empire-forecast-validation"),
    "national_storm_hub_website_release": ("engineering", "empire-engineering-verification"),
    "national_storm_hub_seo_editorial": ("marketing_growth", "empire-seo-intelligence"),
    "national_storm_hub_revenue_pulse": ("finance_capital", "empire-revenue-reconciliation"),
    "national_storm_hub_skill_capture": ("rd_innovation", "empire-skill-authoring"),
}


@pytest.mark.parametrize("component", sorted(EXPECTED))
def test_nsh_routes_to_existing_skillforge_skill_not_duplicate(tmp_path: Path, component: str):
    department, skill_name = EXPECTED[component]
    path = tmp_path / skill_name
    path.mkdir()
    (path / "SKILL.md").write_text("TEST ONLY: not approved\n")
    result = recommend_work_item_skills(
        {"id": "nsh-test", "target_component": component, "department_keys": [department]},
        root=tmp_path,
    )
    assert COMPONENT_TASKS[component] in {
        "evidence_analysis", "predictive_forecast", "engineering_review",
        "seo_research", "revenue_reconciliation", "skill_authoring",
    }
    assert result["mode"] == "OBSERVE"
    assert result["queue_mutated"] is False
    assert result["execution_authority"] == "none"
    recommendation = result["skill_recommendations"][0]
    assert recommendation["selection_basis"] == "component_allowlist"
    assert recommendation["department"] == department
    assert [s["name"] for s in recommendation["skills"]] == [skill_name]
    assert recommendation["skills"][0]["status"] == "local_candidate_not_authorized"


def test_nsh_selectors_require_exact_components_not_keyword_guessing(tmp_path: Path):
    for value in ("national_storm_hub_send_push_and_charge", "storm predictor",
                  "national_storm_hub_revenue_pulse;make_payment", "national_storm_hub_"):
        result = recommend_work_item_skills({
            "department_keys": ["unknown_department"],
            "target_component": value,
        }, root=tmp_path)
        assert result["skill_recommendations"][0]["status"] == "unmapped_department"
        assert result["execution_authority"] == "none"


def test_research_skill_can_be_discovered_but_not_executed(tmp_path: Path):
    target = tmp_path / "empire-evidence-verification"
    target.mkdir()
    (target / "SKILL.md").write_text("Candidate, no authorization.")
    report = discover_task_skills("evidence_analysis", root=tmp_path)
    assert report["execution_authority"] == "none"
    assert report["external_download"] is False
    assert all(s["status"] == "local_candidate_not_authorized" for s in report["skills"])


def test_missing_skill_does_not_build_or_authorize_replacement(tmp_path: Path):
    report = recommend_work_item_skills({
        "department_keys": ["engineering"],
        "target_component": "national_storm_hub_website_release",
    }, root=tmp_path)
    assert report["skill_recommendations"][0]["status"] == "missing_local_skills"
    assert report["queue_mutated"] is False
    assert list(tmp_path.iterdir()) == []
