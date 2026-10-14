"""Postfix staging operator probe must never deploy or leak an alias."""
import json
import pytest

from scripts import probe_owned_postfix_staging as probe


def test_staging_probe_writes_private_files_and_self_cleans():
    outcome = probe.fixture_smoke()
    assert outcome["status"] == "OFFLINE_POSTFIX_PROFILE_VERIFIED"
    assert outcome["staged_file_count"] == 3
    assert outcome["staged_files_owner_only"] is True
    assert outcome["stage_was_temporary"] is True
    assert outcome["synthetic_intent_only"] is True
    assert outcome["allowed_recipients"] == 1
    assert outcome["runtime_postfix_parser_verified"] is False
    assert outcome["actual_mta_parser_verified"] is False
    assert outcome["postmap_compiled"] is False
    assert outcome["mta_binary_invoked"] is False
    assert outcome["network_calls"] == 0
    assert outcome["runtime_socket_bound"] is False
    assert outcome["actual_mail_received"] is False
    assert outcome["receiver_deployed"] is False
    assert outcome["producer_signing_key_provisioned"] is False
    assert outcome["bare_reply_mailbox_admitted"] is False
    assert outcome["wildcard_or_catchall_admitted"] is False
    assert outcome["external_relay_enabled"] is False
    assert outcome["smtp_submission_enabled"] is False
    assert outcome["mx_changed"] is False
    assert outcome["mail_sent"] is False
    assert outcome["execution_authority"] == "none"
    assert "reply+00000000" not in str(outcome)


def test_explicit_offline_cli_emits_privacy_safe_contract(capsys):
    assert probe.main(["--fixture-smoke"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "OFFLINE_POSTFIX_PROFILE_VERIFIED"
    assert result["allowed_recipients"] == 1
    assert result["network_calls"] == 0
    assert result["runtime_socket_bound"] is False


def test_default_never_creates_staging_files(monkeypatch, capsys):
    monkeypatch.setattr(
        probe, "fixture_smoke",
        lambda: pytest.fail("default must not even construct fixture"),
    )
    assert probe.main([]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "STAGING_NOT_REQUESTED"
    assert data["receiver_deployed"] is False
    assert data["mx_changed"] is False
    assert data["network_calls"] == 0


def test_founder_status_staging_does_not_claim_live_receiver():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    data = TestClient(build_founder_dashboard_service()).get(
        "/v1/founder-jev/status"
    ).json()
    assert data["postfix_offline_staging_profile_prepared"] is True
    assert data["postfix_staging_smtp_acceptance_tested"] is False
    assert data["postfix_production_receiver_deployed"] is False
    assert data["sovereign_ingress_mta_deployed"] is False
    assert data["independently_verified_buyer_replies"] is None
    assert data["production_activated"] is False
