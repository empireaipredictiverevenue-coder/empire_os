from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_contact_sync_service_owns_secret_environment_boundary():
    text = (
        ROOT
        / "deploy/systemd/empire-enterprise-contact-sync.service"
    ).read_text()

    assert "Type=oneshot" in text
    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "EnvironmentFile=/etc/empire_os.env" in text
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in text
    assert "run_enterprise_contact_intelligence.py" in text
    assert "refresh_buyer_acquisition_team.py" in text
    assert "verify_enterprise_contact_intelligence.py" in text
    assert "OnFailure=empire-enterprise-contact-repair.service" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "outbound" not in text.lower()
    assert "payment" not in text.lower()


def test_enterprise_contact_verifier_is_fail_closed():
    text = (
        ROOT / "scripts/verify_enterprise_contact_intelligence.py"
    ).read_text()

    assert "buyer_candidate_reviews" in text
    assert '"live_outbound_send": False' in text
    assert '"payment_action": False' in text
    assert '"actual_revenue": False' in text
    assert "reviews_approved" in text
