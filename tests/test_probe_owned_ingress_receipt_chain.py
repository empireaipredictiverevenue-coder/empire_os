"""Sovereign ingress one-shot smoke runs without external services or secrets."""
import json

import pytest

from scripts import probe_owned_ingress_receipt_chain as probe


def test_offline_gauntlet_reaches_existing_signed_jev_verifier():
    output=probe.fixture_smoke()
    assert output["status"]=="OFFLINE_END_TO_END_PASS"
    assert output["signed_receipt_consumer_validated"] is True
    assert output["durable_replay_prevented"] is True
    assert output["synthetic_only"] is True
    assert output["network_calls"]==0
    assert output["actual_mail_sent"] is False
    assert output["actual_smtp_delivery_seen"] is False
    assert output["postfix_deployed"] is False
    assert output["live_ingress_key_provisioned"] is False
    assert output["original_smtp_provider_independently_verified"] is False
    assert output["buyer_reply_count_verified"] is None
    assert output["recognized_revenue"] is None
    assert output["database_writes"] is False
    assert output["dns_changed"] is False
    assert "private@buyer.example" not in repr(output)
    assert "PRIVATE" not in repr(output)


def test_cli_fixture_only_has_no_email_or_network(capsys):
    assert probe.main(["--fixture-smoke"]) == 0
    output=json.loads(capsys.readouterr().out)
    assert output["status"]=="OFFLINE_END_TO_END_PASS"
    assert output["execution_authority"]=="none"


def test_default_has_zero_external_effects(monkeypatch,capsys):
    monkeypatch.setattr(probe,"fixture_smoke",
        lambda: pytest.fail("default must not mint even a fixture key"))
    assert probe.main([])==0
    output=json.loads(capsys.readouterr().out)
    assert output["status"]=="NO_LIVE_INGRESS_PROBE_AUTHORIZED"
    assert output["network_calls"]==0
    assert output["actual_mail_sent"] is False


def test_founder_status_does_not_confuse_offline_pipeline_with_live_smtp():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    data=TestClient(build_founder_dashboard_service()).get(
        "/v1/founder-jev/status"
    ).json()
    assert data["sovereign_ingress_receipt_pipeline_tested"] is True
    assert data["sovereign_ingress_mta_deployed"] is False
    assert data["sovereign_ingress_signer_production_audited"] is False
    assert data["first_party_reply_ingress_production_verified"] is False
    assert data["independently_verified_buyer_replies"] is None
    assert data["production_activated"] is False
