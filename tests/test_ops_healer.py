from empire_os.ops_healer import execute_action


def fake_runner(command, timeout):
    return {"returncode": 0, "stdout_tail": "ok", "stderr_tail": ""}


def test_allowlisted_service_restart_executes():
    result = execute_action(
        {
            "action": "restart_unit",
            "target": "empire-public-gateway.service",
            "authority": "internal_write",
        },
        runner=fake_runner,
    )
    assert result["ok"] is True
    assert result["decision"] == "EXECUTED"


def test_arbitrary_service_is_blocked():
    result = execute_action(
        {
            "action": "restart_unit",
            "target": "ssh.service",
            "authority": "internal_write",
        },
        runner=fake_runner,
    )
    assert result["decision"] == "BLOCKED"


def test_non_internal_authority_is_blocked():
    result = execute_action(
        {
            "action": "restart_unit",
            "target": "empire-public-gateway.service",
            "authority": "founder_gate",
        },
        runner=fake_runner,
    )
    assert result["decision"] == "BLOCKED"
