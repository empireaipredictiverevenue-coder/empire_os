from empire_os.astra_executive import (
    CAPABILITY_COMPONENT,
    NBA_COMPONENT,
    QUANT_FIELD_COMPONENT,
)
from empire_os.control_fabric import default_registry
from empire_os.departments import (
    departments_for_component,
    validate_departments,
)


def test_all_department_components_exist_in_control_fabric():
    registry = {row.name for row in default_registry()}
    result = validate_departments(registered_components=registry)
    assert result["all_components_registered"] is True
    assert result["departments_with_missing_components"] == {}


def test_all_astra_delegate_targets_are_registered_and_owned():
    registry = {row.name for row in default_registry()}
    targets = {
        *CAPABILITY_COMPONENT.values(),
        *NBA_COMPONENT.values(),
        *QUANT_FIELD_COMPONENT.values(),
        "ops_sentinel",
        "predictive_cloud_opportunity_loop",
    }
    missing = sorted(targets - registry)
    assert missing == []

    unowned = sorted(
        component
        for component in targets
        if not departments_for_component(component)
    )
    assert unowned == []


def test_quant_stays_nonexecuting_in_control_fabric():
    by_name = {row.name: row for row in default_registry()}
    assert by_name["quant_brain"].authority == "observe"
    assert by_name["predictive_intelligence"].authority == "observe"


def test_intelligence_router_is_registered_owned_and_nonexecuting():
    by_name = {row.name: row for row in default_registry()}
    assert "intelligence_router" in by_name
    assert by_name["intelligence_router"].authority == "observe"
    owners = departments_for_component("intelligence_router")
    assert "strategy" in owners
    assert "rd_innovation" in owners
    assert "engineering" in owners
