from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_activation_service_is_manual_observe_only():
    text = (
        ROOT
        / "deploy/systemd/"
        "empire-predictive-revenue-enterprise-activation.service"
    ).read_text()

    assert "Type=oneshot" in text
    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in text
    assert "activate_predictive_revenue_enterprise_targets.py" in text
    assert "refresh_buyer_acquisition_team.py" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "outbound" not in text.lower()
    assert "payment" not in text.lower()
