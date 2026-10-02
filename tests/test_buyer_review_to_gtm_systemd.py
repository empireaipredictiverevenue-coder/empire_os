from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_materializer_success_triggers_gtm_pipeline():
    text = (
        ROOT / "deploy/systemd/empire-buyer-review-materializer.service"
    ).read_text()
    assert "OnSuccess=empire-gtm-pipeline.service" in text


def test_gtm_timer_is_fallback_not_primary_cadence():
    text = (
        ROOT / "deploy/systemd/empire-gtm-pipeline.timer"
    ).read_text()
    assert "OnUnitActiveSec=15min" in text
    assert "Unit=empire-gtm-pipeline.service" in text
