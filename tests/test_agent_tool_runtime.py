from pathlib import Path

from empire_os.agent_tool_runtime import (
    agent_reach_health,
    pi_health,
    space_agent_health,
)


def test_missing_external_tools_fail_closed(tmp_path):
    assert pi_health(tmp_path / "missing-pi").ready is False
    assert space_agent_health(tmp_path / "missing-space").ready is False

    reach = agent_reach_health(tmp_path / "missing-reach")
    assert reach["tool"]["ready"] is False
    assert reach["truth_authority"] == "none"


def test_agent_reach_health_never_promotes_doctor_to_truth(tmp_path):
    reach = agent_reach_health(tmp_path / "missing")
    assert reach["truth_authority"] == "none"
