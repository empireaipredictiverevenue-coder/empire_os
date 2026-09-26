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


def test_enterprise_contact_deployer_retries_once_after_verified_self_repair():
    text = (
        ROOT / "scripts/deploy_enterprise_contact_intelligence.sh"
    ).read_text()

    assert "=== AUTOMATIC REPAIR ATTEMPT ===" in text
    assert "EMPIRE_CONTACT_DEPLOY_REENTRY" in text
    assert "RESOLVED_AND_PUSHED" in text
    assert "RESOLVED_BY_CONCURRENT_CHANGE" in text
    assert "Retrying deployment once" in text
    assert "exec bash scripts/deploy_enterprise_contact_intelligence.sh" in text
    assert "repaired deployment already retried once" in text


def test_enterprise_contact_deployer_surfaces_coder_repair_error():
    text = (
        ROOT / "scripts/deploy_enterprise_contact_intelligence.sh"
    ).read_text()

    assert '"CODER_REPAIR_FAILED"' in text
    assert "Repair controller error:" in text
    assert 'payload.get("error")' in text


def test_enterprise_contact_deployer_suppresses_live_banner_on_sync_failure():
    text = (
        ROOT / "scripts/deploy_enterprise_contact_intelligence.sh"
    ).read_text()

    assert "STOP: canonical enterprise contact sync is not healthy." in text
    assert "LIVE banner suppressed; incident retained for repair." in text
    failure_index = text.index(
        "Canonical-env sync did not complete cleanly."
    )
    stop_index = text.index(
        "STOP: canonical enterprise contact sync is not healthy."
    )
    live_index = text.index(
        'echo "ENTERPRISE CONTACT INTELLIGENCE LIVE"'
    )
    assert failure_index < stop_index < live_index
    assert 'exit "${SYNC_RC:-1}"' in text
