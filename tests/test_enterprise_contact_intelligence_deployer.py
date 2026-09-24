from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_contact_deployer_tests_installs_syncs_and_starts_async():
    text = (
        ROOT / "scripts/deploy_enterprise_contact_intelligence.sh"
    ).read_text()

    assert "tests/test_enterprise_contact_intelligence.py" in text
    assert "tests/test_enterprise_targeted_retry.py" in text
    assert "tests/test_enterprise_contact_repair.py" in text
    assert "install_enterprise_contact_intelligence.sh" in text
    assert "run_enterprise_contact_intelligence.py" in text
    assert "run_enterprise_contact_repair.py" in text
    assert "--record-test-log" in text
    assert "refresh_buyer_acquisition_team.py" in text
    assert (
        "systemctl start --no-block "
        "empire-buyer-deferred-enrichment.service"
        in text
    )
    assert "empire-enterprise-contact-repair.service" in text
    assert '"reviews_approved"] == 0' in text
    assert '"live_outbound_send"] is False' in text
    assert '"payment_action"] is False' in text
    assert '"actual_revenue"] is False' in text


def test_enterprise_contact_deployer_uses_canonical_systemd_env_for_sync():
    text = (
        ROOT / "scripts/deploy_enterprise_contact_intelligence.sh"
    ).read_text()

    assert "systemctl start empire-enterprise-contact-sync.service" in text
    assert "verify_enterprise_contact_intelligence.py" in text
    assert "SYNC_RESULT" in text
    assert "EnvironmentFile" not in text
