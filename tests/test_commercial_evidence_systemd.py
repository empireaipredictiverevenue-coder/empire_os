from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_commercial_evidence_verifier_service_uses_bounded_existing_worker():
    text = (
        ROOT
        / "deploy/systemd/empire-commercial-evidence-auto-verifier.service"
    ).read_text()

    assert "run_commercial_evidence_auto_verifier.py" in text
    assert "--limit 50" in text
    assert "EnvironmentFile=/etc/empire_os.env" in text
    assert "outbound_governor" not in text
    assert "voice_outbound" not in text


def test_commercial_evidence_verifier_timer_is_persistent():
    text = (
        ROOT
        / "deploy/systemd/empire-commercial-evidence-auto-verifier.timer"
    ).read_text()

    assert "OnUnitInactiveSec=5min" in text
    assert "Persistent=true" in text
