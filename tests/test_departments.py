from empire_os.departments import (
    default_departments,
    departments_for_component,
    validate_departments,
)


def test_canonical_departments_include_marketing_and_rd():
    by_key = {row.key: row for row in default_departments()}
    assert "marketing_growth" in by_key
    assert "rd_innovation" in by_key
    assert by_key["marketing_growth"].blueprint_refs == (
        "docs/MARKETING_DEPARTMENT_BLUEPRINT.md",
    )
    assert by_key["rd_innovation"].blueprint_refs == (
        "docs/RD_DEPARTMENT_BLUEPRINT.md",
    )


def test_agents_are_roles_inside_departments_not_departments_themselves():
    by_key = {row.key: row for row in default_departments()}
    assert "marketing" in by_key["marketing_growth"].agent_roles
    assert "growth" in by_key["marketing_growth"].agent_roles
    assert "research" in by_key["rd_innovation"].agent_roles
    assert "engineering" in by_key["rd_innovation"].agent_roles


def test_component_can_serve_multiple_departments():
    departments = departments_for_component("quant_brain")
    assert "data_quant" in departments
    assert "finance_capital" in departments


def test_validation_reports_unregistered_department_components():
    result = validate_departments(
        registered_components={"astra_executive", "astra", "control_fabric"}
    )
    assert result["all_components_registered"] is False
    assert "marketing_growth" in result[
        "departments_with_missing_components"
    ]
