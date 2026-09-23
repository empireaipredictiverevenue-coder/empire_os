from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy/systemd/empire-media-os.service"
TIMER = ROOT / "deploy/systemd/empire-media-os.timer"


def test_media_os_runtime_service_is_internal_and_unprivileged():
    text = SERVICE.read_text()

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "refresh_media_os_runtime.py" in text

    lowered = text.lower()
    assert "publish" not in lowered
    assert "youtube.com/upload" not in lowered
    assert "curl " not in lowered
    assert "environmentfile=" not in lowered


def test_media_os_runtime_timer_is_bounded():
    text = TIMER.read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text
    assert "Unit=empire-media-os.service" in text
