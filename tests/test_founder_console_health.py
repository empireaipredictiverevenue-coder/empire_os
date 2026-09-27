import signal

from empire_os import founder_console_health as health


def _identity(*, cgroup: str):
    return {
        "exists": True,
        "uid": health.os.getuid(),
        "cwd": str(health.FOUNDER_CONSOLE_APP),
        "command": "next-server (v16.3.5)",
        "cgroup": cgroup,
        "start_ticks": "12345",
    }


def test_legacy_user_scope_is_verified_as_orphan_candidate():
    identity = _identity(
        cgroup=(
            "0::/user.slice/user-1000.slice/"
            "user@1000.service/app.slice/"
            "empire-founder-console.service"
        )
    )

    assert health._legacy_user_scope(identity) is True
    assert health._canonical_system_scope(identity) is False
    assert health._verified_console_process(identity) is True


def test_canonical_system_scope_is_never_treated_as_orphan():
    identity = _identity(
        cgroup="0::/system.slice/empire-founder-console.service"
    )

    assert health._canonical_system_scope(identity) is True
    assert health._verified_console_process(identity) is False


def test_legacy_user_unit_is_disabled_before_process_termination():
    observation = health.FounderConsoleObservation(
        service_state="activating",
        http_ok=True,
        port_pid=4242,
        port_process_verified=True,
        port_process_cwd=str(health.FOUNDER_CONSOLE_APP),
        port_process_command="next-server (v16.3.5)",
        port_process_cgroup=(
            "0::/user.slice/user-1000.slice/"
            "user@1000.service/app.slice/"
            "empire-founder-console.service"
        ),
        legacy_user_scope=True,
    )

    events = []
    alive = {"value": True}

    def stopper():
        events.append("stop-user-unit")
        return {"ok": True}

    def identity(_pid):
        return _identity(
            cgroup=(
                "0::/user.slice/user-1000.slice/"
                "user@1000.service/app.slice/"
                "empire-founder-console.service"
            )
        )

    def killer(_pid, sig):
        events.append(("kill", sig))
        if sig == signal.SIGTERM:
            alive["value"] = False

    result = health.clear_verified_orphan(
        observation,
        sleep=lambda _seconds: None,
        user_unit_stopper=stopper,
        process_identity=identity,
        process_exists=lambda _pid: alive["value"],
        kill_process=killer,
    )

    assert result["ok"] is True
    assert result["state"] == "ORPHAN_TERMINATED"
    assert events[0] == "stop-user-unit"
    assert events[1] == ("kill", signal.SIGTERM)


def test_failed_user_unit_stop_blocks_kill():
    observation = health.FounderConsoleObservation(
        service_state="activating",
        http_ok=True,
        port_pid=4242,
        port_process_verified=True,
        port_process_cwd=str(health.FOUNDER_CONSOLE_APP),
        port_process_command="next-server",
        port_process_cgroup=(
            "0::/user.slice/user-1000.slice/"
            "user@1000.service/app.slice/"
            "empire-founder-console.service"
        ),
        legacy_user_scope=True,
    )

    killed = []

    result = health.clear_verified_orphan(
        observation,
        user_unit_stopper=lambda: {"ok": False},
        kill_process=lambda pid, sig: killed.append((pid, sig)),
    )

    assert result["ok"] is False
    assert result["state"] == "LEGACY_USER_UNIT_STOP_FAILED"
    assert killed == []
