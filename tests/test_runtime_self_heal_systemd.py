from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_self_heal_service_is_observe_only_and_internal():
    text = (
        ROOT / "deploy/systemd/empire-runtime-self-heal.service"
    ).read_text()

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in text
    assert "run_runtime_self_heal.py" in text
    assert "empire-ops-privileged-helper.service" in text
    assert "outbound" not in text.lower()
    assert "payment" not in text.lower()


def test_runtime_self_heal_timer_is_persistent_and_bounded():
    text = (
        ROOT / "deploy/systemd/empire-runtime-self-heal.timer"
    ).read_text()

    assert "OnUnitInactiveSec=2min" in text
    assert "Persistent=true" in text
    assert "empire-runtime-self-heal.service" in text
