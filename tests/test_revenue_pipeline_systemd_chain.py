from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_enrichment_hands_off_to_review_materializer():
    text = (
        ROOT / "deploy/systemd/empire-buyer-deferred-enrichment.service"
    ).read_text()
    assert "OnSuccess=empire-buyer-review-materializer.service" in text


def test_review_materializer_hands_off_to_gtm():
    text = (
        ROOT / "deploy/systemd/empire-buyer-review-materializer.service"
    ).read_text()
    assert "OnSuccess=empire-gtm-pipeline.service" in text


def test_review_materializer_timer_is_fallback_only():
    text = (
        ROOT / "deploy/systemd/empire-buyer-review-materializer.timer"
    ).read_text()
    assert "OnUnitActiveSec=15min" in text
    assert "Unit=empire-buyer-review-materializer.service" in text
