from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/verify_outbound_production_readiness.sh"


def test_production_readiness_probe_is_read_only():
    text = PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "no migration / no role change / no service change / no send" in lowered
    assert "outbound_release_attestation" in text
    assert "EMPIRE_OUTBOUND_EXPECTED_SHA" in text
    assert "release_sha=\"$(git rev-parse HEAD)\"" in text
    assert "outbound_ringleader_preflight" in text
    assert "outbound_ringleader_watchdog" in text
    assert "outbound_empiredb_activation_probe" in text
    assert "http://127.0.0.1:8097/health" in text

    for forbidden in (
        "systemctl start ",
        "systemctl restart ",
        "systemctl enable ",
        "systemctl disable ",
        "systemctl stop ",
        "psql ",
        "cloudflare",
        "claim_outbound_send",
        "approve_outbound_intent",
    ):
        assert forbidden not in lowered

    assert "database_activation_authorized=false" in text
    assert "service_activation_authorized=false" in text
    assert "dns_mutation_authorized=false" in text
    assert "provisioning_authorized=false" in text
    assert "send_authorized=false" in text


def test_production_readiness_probe_fails_closed_on_missing_db_probe_dsn():
    text = PATH.read_text(encoding="utf-8")
    assert "EMPIRE_OUTBOUND_ACTIVATION_PROBE_DSN" in text
    assert "EMPIREDB_MIGRATOR_DSN" in text
    assert "RESULT: BLOCKED" in text
    assert "exit 2" in text
