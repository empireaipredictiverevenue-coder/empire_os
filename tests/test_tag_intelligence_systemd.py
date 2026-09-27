from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tag_intelligence_service_is_observe_only_runtime_writer():
    text = (
        ROOT / "deploy/systemd/empire-tag-intelligence.service"
    ).read_text()

    assert "refresh_tag_intelligence_monitor.py" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_tag_intelligence_timer_runs_every_six_hours():
    text = (
        ROOT / "deploy/systemd/empire-tag-intelligence.timer"
    ).read_text()

    assert "OnUnitInactiveSec=6h" in text
    assert "Persistent=true" in text



def test_tag_intelligence_service_has_safe_default_public_target():
    text = (
        ROOT / "deploy/systemd/empire-tag-intelligence.service"
    ).read_text()

    assert (
        "EMPIRE_TAG_MONITOR_URLS=https://empire-ai.co.uk"
        in text
    )
