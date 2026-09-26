import pytest

from empire_os.system_demo_recorder import (
    DemoAction,
    DemoRecordingPlan,
    founder_console_demo_plan,
)


def test_founder_console_plan_records_real_loopback_ui():
    plan = founder_console_demo_plan()
    plan.validate()
    assert plan.base_url == "http://127.0.0.1:8775"
    assert plan.actions[0].action == "goto"
    assert plan.actions[0].value == "/founder"
    assert any(action.action == "scroll" for action in plan.actions)


def test_non_loopback_target_is_rejected():
    plan = DemoRecordingPlan(
        title="bad",
        base_url="https://example.com",
        actions=(DemoAction("goto", "/founder"),),
    )
    with pytest.raises(ValueError, match="loopback"):
        plan.validate()


def test_click_requires_selector():
    with pytest.raises(ValueError, match="requires value"):
        DemoAction("click", "").validate()


def test_recording_plan_rejects_empty_actions():
    plan = DemoRecordingPlan(
        title="bad",
        base_url="http://127.0.0.1:8775",
        actions=(),
    )
    with pytest.raises(ValueError, match="at least one action"):
        plan.validate()
