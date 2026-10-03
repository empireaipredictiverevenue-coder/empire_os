from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / ".github/workflows/outbound-deliverability.yml"


def test_outbound_ci_tracks_current_production_surfaces():
    text = PATH.read_text(encoding="utf-8")

    for required in (
        "empire_os/resend_webhook_app.py",
        "migrations/empiredb/036_outbound_capacity_reservation_leases.sql",
        "migrations/empiredb/037_outbound_source_reputation_memory.sql",
        "migrations/empiredb/038_outbound_content_claim_memory.sql",
        "migrations/empiredb/039_outbound_fleet_readiness_certificates.sql",
        "migrations/empiredb/040_outbound_account_saturation_dimensions.sql",
        "migrations/empiredb/041_outbound_telemetry_sla.sql",
        "deploy/empiredb/outbound_deliverability_roles.sql",
        "deploy/systemd/empire-outbound-ringleader-watchdog.*",
        "scripts/provision_outbound_deliverability_roles.sh",
        "scripts/verify_outbound_production_readiness.sh",
        "config/outbound_ringleader_context.example.json",
    ):
        assert required in text


def test_outbound_ci_installs_and_tests_resend_runtime_contract():
    text = PATH.read_text(encoding="utf-8")

    assert 'python -m pip install -e ".[dev,outbound-email]"' in text
    assert "empire_os/resend_webhook_app.py" in text
    assert "tests/test_resend_webhook_app.py" in text


def test_outbound_ci_emits_non_authorizing_release_attestation():
    text = PATH.read_text(encoding="utf-8")

    assert "Build outbound release attestation" in text
    assert "Upload outbound release attestation" in text
    assert "outbound_release_attestation.json" in text
    assert '"targeted_ci_green": True' in text
    assert '"compile_green": True' in text
    assert '"tests_green": True' in text
    assert '"founder_ui_typecheck_green": True' in text

    for field in (
        "database_activation_authorized",
        "service_activation_authorized",
        "dns_mutation_authorized",
        "provisioning_authorized",
        "send_authorized",
    ):
        assert f'"{field}": False' in text


def test_release_attestation_is_uploaded_only_after_successful_matrix():
    text = PATH.read_text(encoding="utf-8")
    assert "if: ${{ success() }}" in text
    assert "actions/upload-artifact@v4" in text
    assert "retention-days: 30" in text
