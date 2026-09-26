from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy/systemd/empire-hermes-control.service"
TIMER = ROOT / "deploy/systemd/empire-hermes-control.timer"
LATEST_RUNNER = ROOT / "scripts/run_hermes_resident_latest.sh"


def test_hermes_service_is_unprivileged_and_observe_bounded():
    text = SERVICE.read_text()

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in text
    assert "EMPIRE_HERMES_BIN=/home/ubuntu/.local/bin/hermes" in text
    assert "/home/ubuntu/.local/bin" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ProtectHome=read-only" in text
    assert "RestrictSUIDSGID=true" in text
    assert "run_hermes_resident_latest.sh" in text

    assert "/srv/empire_os/.git" in text
    assert "/srv/empire_os/runtime" in text
    assert "/srv/empire_os/runtime/hermes_control" not in text


def test_hermes_timer_is_bounded():
    text = TIMER.read_text()

    assert "OnUnitInactiveSec=2min" in text
    assert "Persistent=true" in text
    assert "Unit=empire-hermes-control.service" in text


def test_latest_runner_updates_disposable_runtime_worktree_only():
    text = LATEST_RUNNER.read_text()

    assert "git fetch" in text
    assert "feature/revenue-intelligence-v2" in text
    assert "runtime/hermes_control/worker_code" in text
    assert "git worktree add --detach" in text
    assert 'export PYTHONPATH="$WORKTREE"' in text
    assert '"$WORKTREE/scripts/run_hermes_control_worker.py"' in text
    assert "--max-jobs 1" in text

    assert "git merge" not in text
    assert "git checkout" not in text
    assert "git add ." not in text
    assert "recovery/" not in text
    assert "toop/" not in text
