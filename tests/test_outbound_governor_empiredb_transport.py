from pathlib import Path


def test_empiredb_governor_requires_dedicated_sender_and_approver():
    source = Path(
        "scripts/outbound_governor_worker.py"
    ).read_text()

    assert "EmpireDB outbound sender DSN required" in source
    assert "EmpireDB outbound approver DSN required" in source
    assert "PostgresStandingAuthorityApproverRpc" in source


def test_generic_empiredb_provider_does_not_gain_sender_authority():
    source = Path(
        "empire_os/data_backends/empiredb.py"
    ).read_text()

    assert '"claim_outbound_send":' not in source
    assert '"record_outbound_delivery":' not in source
    assert '"auto_approve_outbound_intent":' not in source
    assert '"auto_approve_outbound_followup":' not in source
    assert '"auto_approve_closer_reply_intent":' not in source
