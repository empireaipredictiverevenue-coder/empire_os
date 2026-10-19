"""No invented traffic, cookies or release authority in operator result."""
import json
import pytest

from scripts import review_analytics_session_authority_20261019 as tool


def test_offline_operator_reports_lifecycle_proofs_not_visitor_counts():
    d=tool.inspect()
    assert d["status"]=="OFFLINE_SESSION_CONSENT_AND_HTTP_CONTRACT_VERIFIED"
    assert d["default_consent_denial_test_passed"] is True
    assert d["simulated_server_consent_grant_test_passed"] is True
    assert d["revocation_blocks_repeated_event_test_passed"] is True
    assert d["server_acquisition_resolver_test_passed"] is True
    assert d["production_consent_authority_active"] is False
    assert d["persistent_empiredb_analytics_ledger_active"] is False
    assert d["real_sessions_observed"] is False
    assert d["real_website_analytics_consent_verified"] is False
    assert d["public_analytics_collector_active"] is False
    assert d["database_writes"] is False
    assert d["live_service_changed"] is False
    assert d["tracking_added"] is False
    assert d["execution_authority"]=="NONE"
    assert "session_nonce" not in json.dumps(d)


def test_cli_read_only_and_rejects_mutating_flags(capsys):
    assert tool.main(["--read-only"])==0
    data=json.loads(capsys.readouterr().out)
    assert data["source"]=="local_synthetic_nonpersistent_evidence"
    for flags in ([],["--apply"],["--activate"],["--publish"],
                  ["--read-only","--start-collector"]):
        with pytest.raises(SystemExit):
            tool.main(flags)
