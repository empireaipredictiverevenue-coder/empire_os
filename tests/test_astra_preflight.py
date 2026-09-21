from pathlib import Path

from empire_os.astra_preflight import assess_runtime_preflight


def write_env(path: Path, text: str, mode=0o600):
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def test_missing_env_and_units_are_explicit(tmp_path):
    result = assess_runtime_preflight(
        env_path=tmp_path / ".env.astra_observer",
        service_installed=False,
        timer_installed=False,
        timer_enabled=False,
    )
    assert result.runtime_ready is False
    assert "observer_env_file_missing" in result.blockers
    assert "observer_transport_not_configured" in result.blockers
    assert "observer_service_not_installed" in result.blockers
    assert "observer_timer_not_installed" in result.blockers
    assert "observer_timer_not_enabled" in result.blockers


def test_complete_observe_runtime_is_ready(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=1000",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=true",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is True
    assert result.blockers == ()
    assert result.observe_mode_configured is True
    assert result.observer_dsn_configured is True
    assert result.observer_transport_configured is True
    assert result.policy_bindings_complete is True


def test_insecure_secret_file_permissions_block_readiness(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=1000",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=true",
        ]) + "\n",
        mode=0o644,
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is False
    assert "observer_env_permissions_insecure" in result.blockers


def test_non_observe_mode_is_rejected(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=EXECUTE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=1000",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=true",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is False
    assert "observe_mode_not_configured" in result.blockers


def test_token_rpc_transport_is_ready_without_database_dsn(tmp_path):
    env = tmp_path / ".env.astra_observer"
    token = tmp_path / "astra-token"
    write_env(token, "a" * 64 + "\n")
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_SUPABASE_URL=https://example.supabase.co",
            "EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_test",
            f"EMPIRE_ASTRA_OBSERVER_TOKEN_FILE={token}",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=0",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=false",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=false",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is True
    assert result.observer_dsn_configured is False
    assert result.observer_token_rpc_configured is True
    assert result.observer_transport_configured is True
    assert result.blockers == ()


def test_cron_scheduler_satisfies_persistent_runtime_gate(tmp_path):
    env = tmp_path / ".env.astra_observer"
    token = tmp_path / "astra-token"
    write_env(token, "a" * 64 + "\n")
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_SUPABASE_URL=https://example.supabase.co",
            "EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_test",
            f"EMPIRE_ASTRA_OBSERVER_TOKEN_FILE={token}",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=0",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=false",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=false",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=False,
        timer_installed=False,
        timer_enabled=False,
        cron_scheduler_enabled=True,
    )
    assert result.scheduler_ready is True
    assert result.cron_scheduler_enabled is True
    assert result.runtime_ready is True
    assert "observer_service_not_installed" not in result.blockers
    assert "observer_scheduler_not_enabled" not in result.blockers


def test_insecure_token_file_permissions_block_token_transport(tmp_path):
    env = tmp_path / ".env.astra_observer"
    token = tmp_path / "astra-token"
    write_env(token, "a" * 64 + "\n", mode=0o644)
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_SUPABASE_URL=https://example.supabase.co",
            "EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_test",
            f"EMPIRE_ASTRA_OBSERVER_TOKEN_FILE={token}",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=0",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=false",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=false",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=False,
        timer_installed=False,
        timer_enabled=False,
        cron_scheduler_enabled=True,
    )
    assert result.runtime_ready is False
    assert result.observer_token_rpc_configured is True
    assert result.observer_token_file_exists is True
    assert result.observer_token_permissions_secure is False
    assert "observer_token_permissions_insecure" in result.blockers
    assert "observer_transport_not_configured" in result.blockers



def test_source_health_file_can_satisfy_policy_binding(tmp_path):
    env = tmp_path / ".env.astra_observer"
    health = tmp_path / "source-health.json"
    token = tmp_path / "astra-token"
    write_env(token, "a" * 64 + "\n")
    health.write_text(
        '{"observed_at":"2026-09-21T16:00:00+00:00","end_to_end_healthy":true}'
    )
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_SUPABASE_URL=https://example.supabase.co",
            "EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_test",
            f"EMPIRE_ASTRA_OBSERVER_TOKEN_FILE={token}",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=0",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            f"EMPIRE_ASTRA_SOURCE_HEALTH_FILE={health}",
            "EMPIRE_ASTRA_SOURCE_HEALTH_MAX_AGE_SECONDS=1800",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.policy_bindings_complete is True
    assert result.runtime_ready is True
    assert result.blockers == ()


def test_missing_source_health_file_fails_preflight(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=0",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            f"EMPIRE_ASTRA_SOURCE_HEALTH_FILE={tmp_path / 'missing.json'}",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is False
    assert "source_health_file_missing" in result.blockers
    assert "policy_bindings_incomplete" in result.blockers
