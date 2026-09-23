from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tag_service_refreshes_monitor_then_predictive_cloud():
    text = (
        ROOT / "deploy/systemd/empire-tag-intelligence.service"
    ).read_text(encoding="utf-8")

    monitor = (
        "scripts/refresh_tag_intelligence_monitor.py "
        "--repo-root /srv/empire_os"
    )
    status = (
        "scripts/refresh_predictive_cloud_status.py "
        "--repo-root /srv/empire_os"
    )

    assert monitor in text
    assert status in text
    assert text.index(monitor) < text.index(status)
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "EMPIRE_TAG_MONITOR_URLS=https://empire-ai.co.uk" in text


def test_tag_timer_is_bounded_and_persistent():
    text = (
        ROOT / "deploy/systemd/empire-tag-intelligence.timer"
    ).read_text(encoding="utf-8")

    assert "OnUnitInactiveSec=6h" in text
    assert "Persistent=true" in text
    assert "Unit=empire-tag-intelligence.service" in text
