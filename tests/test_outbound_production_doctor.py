from datetime import datetime, timezone
import json

from empire_os.outbound_production_doctor import collect_production_readiness


NOW = datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc)
SHA = "a" * 40


def sovereign_context():
    return {
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "domain_sovereignty": {
            "domain": "outbound.empire.example",
            "purpose": "prospecting",
            "registrar_account_owned": True,
            "dns_authority_owned": True,
            "mfa_enabled": True,
            "domain_lock_enabled": True,
            "auto_renew_enabled": True,
            "dns_zone_exported": True,
            "dmarc_rua_empire_owned": True,
            "provider_portable_sender_identity": True,
            "recovery_path_verified": True,
        },
    }


def write_release(path, *, sha=SHA):
    path.write_text(
        json.dumps({
            "schema_version": "1",
            "workflow": "outbound-deliverability",
            "sha": sha,
            "generated_at": NOW.isoformat(),
            "targeted_ci_green": True,
            "compile_green": True,
            "tests_green": True,
            "founder_ui_typecheck_green": True,
            "database_activation_authorized": False,
            "service_activation_authorized": False,
            "dns_mutation_authorized": False,
            "provisioning_authorized": False,
            "send_authorized": False,
        }),
        encoding="utf-8",
    )


def write_heartbeat(path):
    path.write_text(
        json.dumps({
            "schema_version": "1",
            "source": "outbound_ringleader_observer",
            "observed_at": NOW.isoformat(),
            "scope_key": "empire",
            "mode": "OBSERVE",
            "ringleader_posture": "READY",
            "telemetry_posture": "CURRENT",
            "mutation_authorized": False,
            "send_authorized": False,
        }),
        encoding="utf-8",
    )


def base_env(tmp_path):
    release = tmp_path / "attestation.json"
    context = tmp_path / "context.json"
    heartbeat = tmp_path / "heartbeat.json"
    evidence = tmp_path / "evidence.json"

    write_release(release)
    context.write_text(json.dumps(sovereign_context()), encoding="utf-8")
    write_heartbeat(heartbeat)

    return {
        "EMPIRE_OUTBOUND_RINGLEADER_MODE": "OBSERVE",
        "EMPIRE_OUTBOUND_SCOPE_KEY": "empire",
        "EMPIRE_OUTBOUND_TELEMETRY_SOURCE": "resend",
        "RESEND_API_KEY": "re_test",
        "EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE": "false",
        "EMPIRE_OUTBOUND_ENABLE_ESTATE_RECONCILIATION": "false",
        "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_PATH": str(release),
        "EMPIRE_OUTBOUND_RINGLEADER_CONTEXT_PATH": str(context),
        "EMPIRE_OUTBOUND_OBSERVER_HEARTBEAT_PATH": str(heartbeat),
        "EMPIRE_OUTBOUND_EVIDENCE_BUNDLE_PATH": str(evidence),
    }


def systemd_runner(*, failed_unit=None):
    def run(args):
        if args[:2] == ["systemctl", "is-active"]:
            unit = args[2]
            if unit == failed_unit:
                return 0, "failed"
            if unit.endswith(".timer") or unit == "empire-resend-inbound.service":
                return 0, "active"
            return 0, "inactive"
        if args[:2] == ["systemctl", "is-enabled"]:
            return 0, "enabled"
        if args[:3] == ["systemctl", "show", args[2]]:
            unit = args[2]
            if "--property=Result" in args:
                return 0, "failed" if unit == failed_unit else "success"
            if "--property=ExecMainStatus" in args:
                return 0, "1" if unit == failed_unit else "0"
        if args == ["git", "rev-parse", "HEAD"]:
            return 0, SHA
        return 1, ""
    return run


def provider_ready(*_args, **_kwargs):
    return {
        "source": "provider_event_ingest",
        "observed_at": NOW.isoformat(),
        "success": True,
        "coverage": True,
        "details": {"provider": "resend"},
    }


def db_ready(_dsn):
    return {
        "status": "READY",
        "schema_ready": True,
        "roles_ready": True,
        "privileges_ready": True,
        "mutation_authorized": False,
    }


def test_doctor_accepts_successful_inactive_oneshot_services(tmp_path):
    result = collect_production_readiness(
        base_env(tmp_path),
        now=NOW,
        expected_sha=SHA,
        command_runner=systemd_runner(),
        provider_probe=provider_ready,
        empiredb_probe=db_ready,
    )
    assert result["status"] == "READY"
    assert result["activation_readiness"]["observe"]["status"] == "READY"
    assert result["activation_readiness"]["operational_observe"]["status"] == "READY"
    assert result["activation_readiness"]["live_send"]["status"] == "BLOCKED"
    assert result["systemd"]["empire-outbound-ringleader-observer.service"][
        "active_state"
    ] == "inactive"
    assert result["systemd"]["empire-outbound-ringleader-observer.service"][
        "healthy"
    ] is True
    assert result["send_authorized"] is False


def test_doctor_blocks_exact_sha_mismatch(tmp_path):
    env = base_env(tmp_path)
    write_release(
        __import__("pathlib").Path(env["EMPIRE_OUTBOUND_RELEASE_ATTESTATION_PATH"]),
        sha="b" * 40,
    )
    result = collect_production_readiness(
        env,
        now=NOW,
        expected_sha=SHA,
        command_runner=systemd_runner(),
        provider_probe=provider_ready,
        empiredb_probe=db_ready,
    )
    assert result["status"] == "BLOCKED"
    assert result["release_attestation"]["status"] == "INVALID"
    assert "attestation_sha_mismatch" in result["release_attestation"]["errors"]
    assert "targeted_ci_not_green" in result["activation_readiness"]["observe"]["blockers"]


def test_doctor_blocks_failed_observer_oneshot(tmp_path):
    result = collect_production_readiness(
        base_env(tmp_path),
        now=NOW,
        expected_sha=SHA,
        command_runner=systemd_runner(
            failed_unit="empire-outbound-ringleader-observer.service"
        ),
        provider_probe=provider_ready,
        empiredb_probe=db_ready,
    )
    assert result["status"] == "BLOCKED"
    assert (
        "observer_service_not_healthy"
        in result["activation_readiness"]["operational_observe"]["blockers"]
    )


def test_doctor_blocks_when_provider_event_ingest_is_not_ready(tmp_path):
    def not_ready(*_args, **_kwargs):
        return {
            "source": "provider_event_ingest",
            "observed_at": NOW.isoformat(),
            "success": True,
            "coverage": False,
            "details": {"provider": "resend"},
        }

    result = collect_production_readiness(
        base_env(tmp_path),
        now=NOW,
        expected_sha=SHA,
        command_runner=systemd_runner(),
        provider_probe=not_ready,
        empiredb_probe=db_ready,
    )
    assert result["status"] == "BLOCKED"
    assert (
        "provider_event_ingest_not_ready"
        in result["activation_readiness"]["operational_observe"]["blockers"]
    )


def test_persistence_required_blocks_when_empiredb_not_ready(tmp_path):
    env = base_env(tmp_path)
    env["EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE"] = "true"
    env["EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN"] = "reader"
    env["EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN"] = "writer"
    env["EMPIRE_OUTBOUND_ACTIVATION_PROBE_DSN"] = "probe"

    def db_blocked(_dsn):
        return {
            "status": "BLOCKED",
            "schema_ready": False,
            "roles_ready": False,
            "privileges_ready": False,
            "mutation_authorized": False,
        }

    result = collect_production_readiness(
        env,
        now=NOW,
        expected_sha=SHA,
        command_runner=systemd_runner(),
        provider_probe=provider_ready,
        empiredb_probe=db_blocked,
    )
    assert result["status"] == "BLOCKED"
    blockers = result["activation_readiness"]["observe"]["blockers"]
    assert "empiredb_deliverability_migrations_not_applied" in blockers
    assert "empiredb_deliverability_roles_not_bound" in blockers
